"""Preregistered analysis helpers for Capability Attribution Ablation v1."""

from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from typing import Iterable

from benchmark.capability_attribution import contrast_statistics, material_effect
from benchmark.statistics import holm_adjust


CONDITIONS = {
    "authority": ("M0P0", "M1P0", "M0P1", "M1P1"),
    "provenance": ("M0P0", "M1P0", "M0P1", "M1P1"),
    "temporal": ("C0-native", "C1-assisted"),
    "scope": ("D0-native", "D1-assisted"),
}

PRIMARY = {
    "authority": ("M0P0", "M1P1", "reader_correct"),
    "provenance": ("M0P0", "M1P1", "reader_correct"),
    "temporal": ("C0-native", "C1-assisted", "reader_correct"),
    "scope": ("D0-native", "D1-assisted", "reader_correct"),
}

BLIND_LABELS = {
    "M0P0": "CELL-A",
    "M1P0": "CELL-B",
    "M0P1": "CELL-C",
    "M1P1": "CELL-D",
    "C0-native": "CELL-A",
    "C1-assisted": "CELL-B",
    "D0-native": "CELL-A",
    "D1-assisted": "CELL-B",
}


def validate_test_completeness(
    rows: list[dict],
    *,
    providers: Iterable[str],
    packs: Iterable[str],
    selected: dict[str, str],
    replicates: int = 3,
) -> None:
    """Fail closed on duplicate, missing, or unexpected TEST reader cells."""
    keys = [
        (row["provider"], row["pack"], row["query_id"], int(row["replicate"]), row["condition"])
        for row in rows
    ]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate TEST reader cells")

    expected: set[tuple] = set()
    for provider in providers:
        for pack in packs:
            for query_id, property_name in selected.items():
                if not query_id.startswith(pack.replace("-", "") + "_"):
                    continue
                if property_name == "deletion" or (property_name == "temporal" and provider == "hindsight"):
                    continue
                for replicate in range(1, replicates + 1):
                    for condition in CONDITIONS[property_name]:
                        expected.add((provider, pack, query_id, replicate, condition))
    actual = set(keys)
    missing = sorted(expected - actual)
    unexpected = sorted(actual - expected)
    if missing:
        raise ValueError(f"missing TEST reader cells: {missing[:5]} ({len(missing)} total)")
    if unexpected:
        raise ValueError(f"unexpected TEST reader cells: {unexpected[:5]} ({len(unexpected)} total)")


def _condition_rates(rows: list[dict]) -> dict:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[row["condition"]].append(row)
    result = {}
    for condition, values in sorted(grouped.items()):
        result[condition] = {
            "attempts": len(values),
            "queries": len({(row["pack"], row["query_id"]) for row in values}),
            "reader_correct": round(sum(bool(row["reader_correct"]) for row in values) / len(values), 6),
            "abstention": round(sum(bool(row.get("reader_abstained")) for row in values) / len(values), 6),
            "reader_errors": sum(bool(row.get("reader_error")) for row in values),
            "wrong_authority_selection": sum(int(row.get("wrong_authority_selection", 0)) for row in values),
            "future_evidence_count": sum(int(row.get("future_evidence_count", 0)) for row in values),
            "future_answer_leakage": sum(int(row.get("future_answer_leakage", 0)) for row in values),
            "cross_principal_evidence_count": sum(int(row.get("cross_principal_evidence_count", 0)) for row in values),
            "unauthorized_answer": sum(int(bool(row.get("unauthorized_answer"))) for row in values),
        }
    return result


def _contrast(rows: list[dict], a: str, b: str, metric: str, resamples: int, seed: int) -> dict:
    return contrast_statistics(rows, a, b, metric=metric, resamples=resamples, seed=seed)


def analyze_attempts(rows: list[dict], *, resamples: int = 10_000, seed: int = 20260805) -> dict:
    """Compute all frozen contrasts, Holm correction, and practical materiality."""
    result: dict = {"schema": "sovbench/capability-attribution-analysis/1", "properties": {}}
    by_property_provider: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in rows:
        by_property_provider[(row["property"], row["provider"])].append(row)

    primary_refs: dict[str, list[tuple[str, dict]]] = defaultdict(list)
    for (property_name, provider), values in sorted(by_property_provider.items()):
        a, b, metric = PRIMARY[property_name]
        primary = _contrast(values, a, b, metric, resamples, seed)
        entry = {
            "conditions": _condition_rates(values),
            "primary": primary,
        }
        if property_name in ("authority", "provenance"):
            metadata = _contrast(values, "M0P0", "M1P0", metric, resamples, seed)
            prompt = _contrast(values, "M0P0", "M0P1", metric, resamples, seed)
            entry.update(
                {
                    "metadata_neutral": metadata,
                    "prompt_text_only": prompt,
                    "metadata_governance_prompt": _contrast(values, "M0P1", "M1P1", metric, resamples, seed),
                    "prompt_with_metadata": _contrast(values, "M1P0", "M1P1", metric, resamples, seed),
                    "interaction_delta": round(
                        primary["absolute_delta"] - metadata["absolute_delta"] - prompt["absolute_delta"],
                        6,
                    ),
                }
            )
        entry["answer_change_rate"] = _answer_change_rate(values, a, b)
        result["properties"].setdefault(property_name, {})[provider] = entry
        primary_refs[property_name].append((provider, primary))

    for property_name, references in primary_refs.items():
        adjusted = holm_adjust([item[1]["mcnemar"]["p_value"] for item in references])
        for (provider, stats), p_value in zip(references, adjusted):
            stats["holm_p_value"] = p_value
            stats["material"] = material_effect(stats, holm_p_value=p_value)
            result["properties"][property_name][provider]["primary"] = stats
    return result


def _answer_change_rate(rows: list[dict], condition_a: str, condition_b: str) -> float:
    indexed = {
        (row["pack"], row["query_id"], int(row["replicate"]), row["condition"]): row
        for row in rows
        if row["condition"] in (condition_a, condition_b)
    }
    keys = sorted({key[:3] for key in indexed})
    paired = [
        key for key in keys
        if key + (condition_a,) in indexed and key + (condition_b,) in indexed
    ]
    if not paired:
        return 0.0
    changes = sum(
        indexed[key + (condition_a,)].get("answer") != indexed[key + (condition_b,)].get("answer")
        for key in paired
    )
    return round(changes / len(paired), 6)


def blind_analysis(value):
    """Replace interpretable condition labels for the first analysis pass."""
    blinded = deepcopy(value)

    def visit(node):
        if isinstance(node, dict):
            return {key: visit(BLIND_LABELS.get(item, item) if key in ("condition_a", "condition_b") else item) for key, item in node.items()}
        if isinstance(node, list):
            return [visit(item) for item in node]
        if isinstance(node, str):
            return BLIND_LABELS.get(node, node)
        return node

    return visit(blinded)
