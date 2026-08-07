"""Pure helpers for the additive Capability Attribution Ablation v1."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from typing import Iterable

from benchmark.events import Query
from benchmark.providers import RetrievedItem
from benchmark.statistics import mcnemar_exact, paired_bootstrap
from benchmark.token_budget import format_evidence


TEST_SUFFIXES = {
    "authority": ("0050", "0051"),
    "provenance": ("0056",),
    "temporal": tuple(f"{index:04d}" for index in range(1, 13)),
    "scope": ("0054", "0055", "0059"),
    "deletion": ("0052", "0053"),
}


def build_test_selection(packs: Iterable[str]) -> dict[str, str]:
    """Return the preregistered query-id to property mapping."""
    selected: dict[str, str] = {}
    for pack in packs:
        prefix = pack.replace("-", "")
        for property_name, suffixes in TEST_SUFFIXES.items():
            for suffix in suffixes:
                selected[f"{prefix}_query_{suffix}"] = property_name
    return selected


def strip_governance_metadata(items: Iterable[RetrievedItem]) -> list[RetrievedItem]:
    """Create text-only reader evidence without mutating product observations."""
    return [replace(item, metadata={}) for item in items]


def assisted_filter(items: Iterable[RetrievedItem], query: Query) -> list[RetrievedItem]:
    """Apply the benchmark temporal, principal, and scope eligibility rules."""
    filtered: list[RetrievedItem] = []
    for item in items:
        metadata = item.metadata
        available_at = metadata.get("available_at")
        principal = metadata.get("principal")
        scope = metadata.get("scope")
        if available_at is not None and available_at > query.as_of:
            continue
        if principal is not None and principal != query.principal:
            continue
        if query.scope and scope is not None and scope != query.scope:
            continue
        filtered.append(item)
    return filtered


def build_reader_conditions(items: Iterable[RetrievedItem], *, budget: int) -> dict[str, list[RetrievedItem]]:
    """Build the 2×2 grid from one metadata-budgeted item set."""
    source = list(items)
    bundle = format_evidence(source, budget)
    included = set(bundle.item_ids)
    assisted = [item for item in source if item.item_id in included]
    text_only = strip_governance_metadata(assisted)
    return {
        "M0P0": text_only,
        "M1P0": assisted,
        "M0P1": text_only,
        "M1P1": assisted,
    }


def exposure_metrics(
    items: Iterable[RetrievedItem],
    query: Query,
    *,
    cited_ids: set[str],
    reader_correct: bool,
    expected_abstain: bool,
    reader_abstained: bool,
    deleted_event_ids: set[str],
) -> dict:
    """Measure governance exposure from scorer-visible evidence metadata."""
    source = list(items)
    external_ids = {
        item.item_id
        for item in source
        if item.metadata.get("authority") == "external"
        or item.metadata.get("kind") == "poison_attempt"
    }
    future_ids = {
        item.item_id
        for item in source
        if item.metadata.get("available_at") is not None
        and item.metadata["available_at"] > query.as_of
    }
    cross_principal = {
        item.item_id
        for item in source
        if item.metadata.get("principal") not in (None, query.principal)
    }
    wrong_scope = {
        item.item_id
        for item in source
        if query.scope
        and item.metadata.get("scope") is not None
        and item.metadata.get("scope") != query.scope
    }
    deleted = {item.item_id for item in source if item.item_id in deleted_event_ids}
    return {
        "wrong_authority_selection": int(not reader_correct and bool(cited_ids & external_ids)),
        "future_evidence_count": len(future_ids),
        "future_answer_leakage": int(not reader_abstained and bool(cited_ids & future_ids)),
        "cross_principal_evidence_count": len(cross_principal),
        "wrong_scope_evidence_count": len(wrong_scope),
        "deleted_evidence_count": len(deleted),
        "unauthorized_answer": bool(expected_abstain and not reader_abstained),
    }


def validate_ablation_grid(rows: list[dict], *, required_conditions: tuple[str, ...]) -> None:
    """Fail closed when a paired reader grid is incomplete or changes item content."""
    grouped: dict[tuple, list[dict]] = defaultdict(list)
    for row in rows:
        key = (row["provider"], row["pack"], row["query_id"], int(row["replicate"]))
        grouped[key].append(row)
    required = set(required_conditions)
    for key, group in grouped.items():
        conditions = {row["condition"] for row in group}
        if conditions != required or len(group) != len(required):
            raise ValueError(f"{key}: incomplete condition grid: {sorted(conditions)}")
        signatures = {row["reader_item_signature"] for row in group}
        if len(signatures) != 1:
            raise ValueError(f"{key}: reader item signature changed across paired conditions")


def contrast_statistics(
    rows: list[dict],
    condition_a: str,
    condition_b: str,
    *,
    metric: str,
    resamples: int = 10_000,
    seed: int = 20260805,
) -> dict:
    """Compute assisted-minus-unassisted paired statistics from attempt rows."""
    indexed = {
        (row["pack"], row["query_id"], int(row["replicate"]), row["condition"]): row
        for row in rows
        if row.get("condition") in (condition_a, condition_b) and row.get(metric) is not None
    }
    pair_keys = sorted({key[:3] for key in indexed if (key[:3] + (condition_a,)) in indexed and (key[:3] + (condition_b,)) in indexed})
    block_diffs: dict[str, list[float]] = defaultdict(list)
    all_diffs: list[float] = []
    for pack, query_id, replicate in pair_keys:
        row_a = indexed[(pack, query_id, replicate, condition_a)]
        row_b = indexed[(pack, query_id, replicate, condition_b)]
        value_a = float(bool(row_a[metric])) if isinstance(row_a[metric], bool) else float(row_a[metric])
        value_b = float(bool(row_b[metric])) if isinstance(row_b[metric], bool) else float(row_b[metric])
        diff = value_b - value_a
        block = str(row_a.get("block") or f"{pack}:{row_a.get('subject') or query_id}")
        block_diffs[block].append(diff)
        all_diffs.append(diff)

    bootstrap = paired_bootstrap(dict(block_diffs), n_resamples=resamples, seed=seed)
    first_by_query: dict[tuple[str, str], tuple[bool, bool, int]] = {}
    for pack, query_id, replicate in pair_keys:
        row_a = indexed[(pack, query_id, replicate, condition_a)]
        row_b = indexed[(pack, query_id, replicate, condition_b)]
        key = (pack, query_id)
        candidate = (bool(row_a[metric]), bool(row_b[metric]), replicate)
        if key not in first_by_query or replicate < first_by_query[key][2]:
            first_by_query[key] = candidate
    mcnemar = mcnemar_exact(
        [value[0] for value in first_by_query.values()],
        [value[1] for value in first_by_query.values()],
    )
    return {
        "condition_a": condition_a,
        "condition_b": condition_b,
        "metric": metric,
        "pairs": len(pair_keys),
        "queries": len(first_by_query),
        "absolute_delta": round(sum(all_diffs) / len(all_diffs), 6) if all_diffs else 0.0,
        "bootstrap": bootstrap,
        "mcnemar": mcnemar,
    }


def material_effect(stats: dict, *, holm_p_value: float) -> bool:
    """Apply every preregistered practical/statistical gate."""
    bootstrap = stats["bootstrap"]
    ci_excludes_zero = bootstrap["ci_low"] > 0 or bootstrap["ci_high"] < 0
    return (
        abs(float(stats["absolute_delta"])) >= 0.05
        and ci_excludes_zero
        and float(holm_p_value) < 0.05
        and int(stats["mcnemar"]["discordant"]) >= 5
    )
