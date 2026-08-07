"""Run the additive Capability Attribution Ablation v1."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
from typing import Callable

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))

from benchmark.capability_attribution import (
    assisted_filter,
    build_reader_conditions,
    build_test_selection,
    exposure_metrics,
    validate_ablation_grid,
)
from benchmark.capability_provider_views import native_retrieve
from benchmark.clock import BenchmarkClock
from benchmark.config import REPO_ROOT, Settings, load_settings
from benchmark.events import Query, load_events, load_ground_truth, load_queries
from benchmark.hashing import hash_dir, sha256_file, sha256_text
from benchmark.model_gateway import get_gateway
from benchmark.providers import RetrievedItem, RetrievalResult
from providers.registry import create_provider
from benchmark.scorer import Scorer
from benchmark.token_budget import format_evidence
from benchmark.snapshots import check_no_mutation


PROTOCOL_DIR = REPO_ROOT / "protocols" / "capability-attribution-v1"
RUN_ROOT = REPO_ROOT / "runs" / "followups" / "capability-attribution-v1"
TEST_ROOT = REPO_ROOT / "scorer_private" / "test-v1"
DEV_ROOT = REPO_ROOT / "datasets" / "dev" / "personal"
PREREG_COMMIT = "4749319"
PRICE_INPUT = 0.14
PRICE_OUTPUT = 0.28


TEMPORAL_KINDS = {
    "current_state",
    "historical",
    "supersession",
    "changed_preference",
    "temporary_validity",
    "expiry",
}

PROPERTY_KINDS = {
    "authority": {"authority_conflict", "poisoning"},
    "provenance": {"provenance"},
    "temporal": TEMPORAL_KINDS,
    "scope": {"role_group", "cross_user"},
    "deletion": {"deletion", "do_not_store"},
}


@dataclass(frozen=True)
class SelectedQuery:
    query: Query
    property_name: str


def select_queries(queries: list[Query], *, split: str, pack: str) -> list[SelectedQuery]:
    """Apply the preregistered category/position selection without outcomes."""
    if split == "test":
        mapping = build_test_selection([pack])
        by_id = {query.query_id: query for query in queries}
        missing = sorted(set(mapping) - set(by_id))
        if missing:
            raise ValueError(f"missing preregistered query IDs: {missing}")
        selected: list[SelectedQuery] = []
        for query_id, property_name in mapping.items():
            query = by_id[query_id]
            if query.kind not in PROPERTY_KINDS[property_name]:
                raise ValueError(
                    f"{query_id}: kind mismatch for {property_name}: {query.kind}"
                )
            selected.append(SelectedQuery(query, property_name))
        return selected
    if split != "dev":
        raise ValueError(f"unknown split: {split}")

    subjects = sorted(
        {
            query.subject
            for query in queries
            if query.subject and query.kind in TEMPORAL_KINDS
        }
    )[:2]
    selected = []
    for query in queries:
        property_name = None
        if query.kind in TEMPORAL_KINDS and query.subject in subjects:
            property_name = "temporal"
        elif query.kind in PROPERTY_KINDS["authority"]:
            property_name = "authority"
        elif query.kind == "provenance":
            property_name = "provenance"
        elif query.kind in PROPERTY_KINDS["scope"]:
            property_name = "scope"
        elif query.kind in PROPERTY_KINDS["deletion"]:
            property_name = "deletion"
        if property_name:
            selected.append(SelectedQuery(query, property_name))
    return selected


def _item_signature(items: list[RetrievedItem]) -> str:
    payload = [
        {"id": item.item_id, "text": item.text, "score": item.score}
        for item in items
    ]
    return sha256_text(json.dumps(payload, sort_keys=True, ensure_ascii=False))


def _budget_items(items: list[RetrievedItem], budget: int) -> list[RetrievedItem]:
    included = set(format_evidence(items, budget).item_ids)
    return [item for item in items if item.item_id in included]


def execute_property(
    *,
    provider_name: str,
    pack: str,
    selected: SelectedQuery,
    raw_items: list[RetrievedItem],
    scorer: Scorer,
    gateways: dict,
    replicates: int,
    token_budget: int,
    deleted_event_ids: set[str],
) -> list[dict]:
    """Execute only the preregistered reader cells for one query."""
    query = selected.query
    property_name = selected.property_name
    if property_name == "deletion":
        return []

    condition_specs: list[tuple[str, list[RetrievedItem], list[RetrievedItem], str, str]] = []
    if property_name in ("authority", "provenance"):
        assisted = assisted_filter(raw_items, query)
        reader_grid = build_reader_conditions(assisted, budget=token_budget)
        full_budgeted = _budget_items(assisted, token_budget)
        for condition in ("M0P0", "M1P0", "M0P1", "M1P1"):
            prompt_name = "governance" if condition.endswith("P1") else "neutral"
            metadata_name = "assisted" if condition.startswith("M1") else "text-only"
            condition_specs.append((condition, reader_grid[condition], full_budgeted, prompt_name, metadata_name))
    elif property_name == "temporal":
        if provider_name not in ("gbrain", "mem0"):
            return []
        for condition, items in (
            ("C0-native", raw_items),
            ("C1-assisted", assisted_filter(raw_items, query)),
        ):
            budgeted = _budget_items(list(items), token_budget)
            condition_specs.append((condition, budgeted, budgeted, "governance", "assisted"))
    elif property_name == "scope":
        for condition, items in (
            ("D0-native", raw_items),
            ("D1-assisted", assisted_filter(raw_items, query)),
        ):
            budgeted = _budget_items(list(items), token_budget)
            condition_specs.append((condition, budgeted, budgeted, "governance", "assisted"))
    else:
        raise ValueError(f"unknown property: {property_name}")

    gold = scorer.gold[query.query_id]
    rows: list[dict] = []
    for replicate in range(1, replicates + 1):
        for condition, reader_items, scoring_items, prompt_name, metadata_name in condition_specs:
            base_row = {
                "provider": provider_name,
                "pack": pack,
                "property": property_name,
                "query_id": query.query_id,
                "subject": query.subject,
                "block": f"{pack}:{query.subject or query.query_id}",
                "kind": query.kind,
                "replicate": replicate,
                "condition": condition,
                "prompt_condition": prompt_name,
                "metadata_condition": metadata_name,
                "reader_item_signature": _item_signature(reader_items),
                "reader_evidence_ids": [item.item_id for item in reader_items],
                "scoring_evidence_ids": [item.item_id for item in scoring_items],
            }
            try:
                response = gateways[prompt_name].generate(
                    query,
                    reader_items,
                    f"capability-attribution-v1-{prompt_name}",
                )
            except Exception as exc:  # failed attempts remain in the denominator
                counts = exposure_metrics(
                    scoring_items,
                    query,
                    cited_ids=set(),
                    reader_correct=False,
                    expected_abstain=gold.abstain,
                    reader_abstained=True,
                    deleted_event_ids=deleted_event_ids,
                )
                counts["unauthorized_answer"] = False
                rows.append(
                    {
                        **base_row,
                        "reader_correct": False,
                        "reader_abstained": None,
                        "abstain_correct": False,
                        "forbidden_evidence_count": sum(
                            1 for item in scoring_items if item.metadata.get("kind") == "poison_attempt"
                        ),
                        "authority_correct": False if query.kind == "authority_conflict" else None,
                        "answer": None,
                        "cited_ids": [],
                        "request_tokens": 0,
                        "response_tokens": 0,
                        "retries": 0,
                        "latency_ms": 0.0,
                        "response_model_id": None,
                        "request_id": None,
                        "reader_error": f"{type(exc).__name__}: {str(exc)[:300]}",
                        **counts,
                    }
                )
                continue
            score = scorer.score_query(
                query,
                RetrievalResult(scoring_items),
                response,
                deleted_event_ids=frozenset(deleted_event_ids),
            )
            cited_ids = set(response.structured.get("evidence_ids") or [])
            exposures = exposure_metrics(
                scoring_items,
                query,
                cited_ids=cited_ids,
                reader_correct=bool(score.reader_correct),
                expected_abstain=gold.abstain,
                reader_abstained=score.reader_abstained,
                deleted_event_ids=deleted_event_ids,
            )
            rows.append(
                {
                    **base_row,
                    "reader_correct": score.reader_correct,
                    "reader_abstained": score.reader_abstained,
                    "abstain_correct": score.abstain_correct,
                    "forbidden_evidence_count": score.forbidden_evidence,
                    "cross_principal_evidence_count": score.cross_principal_evidence,
                    "deleted_evidence_count": score.deleted_evidence,
                    "authority_correct": score.authority_correct,
                    "answer": response.structured.get("answer"),
                    "cited_ids": sorted(cited_ids),
                    "request_tokens": response.request_tokens,
                    "response_tokens": response.response_tokens,
                    "retries": response.retries,
                    "latency_ms": round(response.latency_ms, 3),
                    "response_model_id": response.response_model_id,
                    "request_id": response.request_id,
                    "reader_error": None,
                    **exposures,
                }
            )
    return rows


def _write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True, default=str) + "\n" for row in rows),
        encoding="utf-8",
    )


def _git_value(*args: str) -> str:
    result = subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=True)
    return result.stdout.strip()


def _dataset_files(root: Path) -> dict[str, str]:
    return {
        name: f"sha256:{sha256_file(root / name)}"
        for name in ("events.jsonl", "queries.jsonl", "ground_truth.jsonl")
    }


def _validate_test_commitment(pack: str, pack_dir: Path) -> dict:
    commitment = json.loads((REPO_ROOT / "datasets" / "commitments" / "test-v1.json").read_text(encoding="utf-8"))
    expected = commitment["packs"][pack]["files"]
    actual = _dataset_files(pack_dir)
    if actual != expected:
        raise ValueError(f"{pack}: hidden TEST commitment mismatch")
    return {"expected": expected, "actual": actual, "passed": True}


def _dataset_quality(pack: str, events, queries, gold, selected: list[SelectedQuery]) -> dict:
    event_ids = [event.event_id for event in events]
    query_ids = [query.query_id for query in queries]
    selected_ids = [row.query.query_id for row in selected]
    issues: list[str] = []
    if len(event_ids) != len(set(event_ids)):
        issues.append("duplicate event IDs")
    if len(query_ids) != len(set(query_ids)):
        issues.append("duplicate query IDs")
    if set(query_ids) != set(gold):
        issues.append("query/gold key mismatch")
    if len(selected_ids) != len(set(selected_ids)):
        issues.append("duplicate selected query IDs")
    expected = 20 if pack != "dev" else len(selected_ids)
    if len(selected_ids) != expected:
        issues.append(f"selected query count {len(selected_ids)} != {expected}")
    return {
        "pack": pack,
        "events": len(events),
        "queries": len(queries),
        "gold_rows": len(gold),
        "selected_queries": len(selected_ids),
        "selected_ids": selected_ids,
        "issues": issues,
        "passed": not issues,
    }


def _provider_commit(name: str) -> str:
    """Exact upstream pin from the provider registry (single source of truth)."""
    from providers.registry import registry_entry

    entry = registry_entry(name) or {}
    return (entry.get("meta") or {}).get("upstream_commit", "unknown")


def _ledger_summary(path: Path) -> dict:
    if not path.exists():
        return {"requests": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0, "returned_models": []}
    requests = input_tokens = output_tokens = 0
    returned_models: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        usage = entry.get("usage") or {}
        requests += 1
        input_tokens += int(usage.get("prompt_tokens", 0) or 0)
        output_tokens += int(usage.get("completion_tokens", 0) or 0)
        if entry.get("returned_model"):
            returned_models.add(entry["returned_model"])
    cost = (input_tokens * PRICE_INPUT + output_tokens * PRICE_OUTPUT) / 1_000_000
    return {
        "requests": requests,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": round(cost, 6),
        "returned_models": sorted(returned_models),
    }


def _existing_experiment_cost() -> float:
    return round(
        sum(_ledger_summary(path)["cost_usd"] for path in RUN_ROOT.glob("*/**/ledger.jsonl")),
        6,
    )


def _start_proxy(settings: Settings, provider_name: str, ledger_path: Path) -> tuple[str, Callable[[], None]]:
    from benchmark.gateway.ledger import Ledger
    from benchmark.gateway.policy import GatewayPolicy
    from benchmark.gateway.server import create_server

    remaining = round(2.0 - _existing_experiment_cost(), 6)
    if remaining <= 0:
        raise RuntimeError("preregistered USD 2.00 experiment ceiling exhausted")
    policy = GatewayPolicy.load(REPO_ROOT / "config" / "gateway-policy.toml")
    policy.enforce_budget = True
    policy.max_cost_usd_per_run = min(1.0, remaining)
    policy.max_cost_usd_global = remaining
    policy.max_requests_per_run = 1000
    policy.max_requests_global = 1000
    ledger = Ledger(ledger_path)
    upstream_url = os.environ.get("SOVBENCH_PROTOCOL_UPSTREAM_URL", "https://api.deepseek.com/chat/completions")
    proxy = create_server(
        policy=policy,
        ledger=ledger,
        upstream_url=upstream_url,
        api_key=settings.api_key,
        port=0,
        bind_host="127.0.0.1",
        require_identity=True,
    )
    thread = threading.Thread(target=proxy.serve_forever, daemon=True)
    thread.start()

    def stop() -> None:
        proxy.shutdown()
        proxy.server_close()
        thread.join(timeout=5)

    return f"http://127.0.0.1:{proxy.server_port}", stop


def _gateways(reader_mode: str, provider_name: str, provider_root: Path):
    base = load_settings()
    base.gateway_mode = reader_mode
    base.temperature = 0.0
    base.thinking_enabled = False
    base.reasoning_effort = "none"
    base.token_budget = 2048
    base.max_retries = 2
    base.track = "capability-attribution-v1"
    base.identity_run_id = f"capability-attribution-v1-{provider_name}"
    base.identity_provider_id = provider_name
    stop = lambda: None
    ledger_path = provider_root / "ledger.jsonl"
    if reader_mode == "deepseek":
        if not base.api_key:
            raise RuntimeError("SOVBENCH_DEEPSEEK_API_KEY is required for hidden TEST")
        base.gateway_url, stop = _start_proxy(base, provider_name, ledger_path)
    clock = BenchmarkClock("2026-08-01T00:00:00Z")
    neutral_settings = replace(base, prompt_path=PROTOCOL_DIR / "neutral-reader-v1.md")
    governance_settings = replace(base, prompt_path=REPO_ROOT / "prompts" / "reader-v1.md")
    return {
        "neutral": get_gateway(neutral_settings, clock, provider_root / "gateway-neutral.jsonl"),
        "governance": get_gateway(governance_settings, clock, provider_root / "gateway-governance.jsonl"),
    }, stop, ledger_path


def _pack_dir(split: str, pack: str) -> Path:
    return DEV_ROOT if split == "dev" else TEST_ROOT / pack


def _condition_metadata_signature(items: list[RetrievedItem]) -> str:
    payload = [
        {"id": item.item_id, "metadata": item.metadata}
        for item in items
    ]
    return sha256_text(json.dumps(payload, sort_keys=True, default=str))


def run_pack(provider_name: str, split: str, pack: str, gateways: dict, provider_root: Path, ledger_path: Path) -> dict:
    pack_dir = _pack_dir(split, pack)
    run_dir = provider_root / pack
    manifest_path = run_dir / "manifest.json"
    if manifest_path.exists():
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        if existing.get("status") == "completed":
            return existing
        raise RuntimeError(f"{run_dir}: prior incomplete attempt exists; preserve and diagnose before retry")
    run_dir.mkdir(parents=True, exist_ok=False)

    events = load_events(pack_dir / "events.jsonl")
    queries = load_queries(pack_dir / "queries.jsonl")
    gold = load_ground_truth(pack_dir / "ground_truth.jsonl")
    selected = select_queries(queries, split=split, pack=pack)
    quality = _dataset_quality(pack, events, queries, gold, selected)
    if not quality["passed"]:
        raise ValueError(f"{pack}: dataset quality failed: {quality['issues']}")
    commitment = _validate_test_commitment(pack, pack_dir) if split == "test" else {"passed": True, "actual": _dataset_files(pack_dir)}
    scorer = Scorer(gold=gold, version="capability-attribution-v1")

    provider = None
    attempts: list[dict] = []
    retrieval_rows: list[dict] = []
    deletion_rows: list[dict] = []
    manifest = {
        "schema": "sovbench/capability-attribution-run/1",
        "status": "running",
        "split": split,
        "pack": pack,
        "provider": provider_name,
        "provider_commit": _provider_commit(provider_name),
        "preregistration_commit": _git_value("rev-parse", PREREG_COMMIT),
        "code_commit": _git_value("rev-parse", "HEAD"),
        "protocol_hash": hash_dir(PROTOCOL_DIR),
        "dataset_quality": quality,
        "dataset_commitment": commitment,
        "dataset_hashes": _dataset_files(pack_dir),
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    _write_json(manifest_path, manifest)
    try:
        provider = create_provider(provider_name, run_dir / "provider-state")
        upserts = [event for event in events if event.operation == "upsert"]
        lifecycle = [event for event in events if event.operation == "delete"]
        ingest = provider.ingest(upserts)
        provider.await_ready(300)
        delete_outcomes = []
        for event in lifecycle:
            outcome = provider.delete(event.target_event_id)
            delete_outcomes.append({"event_id": event.event_id, "target_event_id": event.target_event_id, "product_delete_returned": bool(outcome)})
        provider.await_ready(300)
        baseline = provider.snapshot()
        deleted_event_ids = {event.target_event_id for event in lifecycle if event.target_event_id}

        for selected_query in selected:
            query = selected_query.query
            if provider_name == "hindsight" and selected_query.property_name == "temporal":
                continue
            before = provider.snapshot()
            if before.state_hash != baseline.state_hash:
                raise RuntimeError(f"{query.query_id}: pre-retrieval state mismatch")
            raw = native_retrieve(provider, query, event_catalog=upserts)
            after = provider.snapshot()
            mutation = check_no_mutation(before, after)
            if not mutation.passed:
                raise RuntimeError(f"{query.query_id}: retrieval mutated provider state")
            assisted = assisted_filter(raw.items, query)
            retrieval_rows.append(
                {
                    "provider": provider_name,
                    "pack": pack,
                    "query_id": query.query_id,
                    "property": selected_query.property_name,
                    "kind": query.kind,
                    "raw_ids": [item.item_id for item in raw.items],
                    "assisted_ids": [item.item_id for item in assisted],
                    "raw_metadata_hash": _condition_metadata_signature(raw.items),
                    "assisted_metadata_hash": _condition_metadata_signature(assisted),
                    "native_scope": raw.raw.get("native_scope"),
                    "state_before": before.state_hash,
                    "state_after": after.state_hash,
                    "mutation_passed": True,
                }
            )
            if selected_query.property_name == "deletion":
                deletion_rows.append(
                    {
                        "provider": provider_name,
                        "pack": pack,
                        "query_id": query.query_id,
                        "kind": query.kind,
                        "raw_ids": [item.item_id for item in raw.items],
                        "assisted_ids": [item.item_id for item in assisted],
                        "deleted_target_ids": sorted(deleted_event_ids),
                        "raw_deleted_evidence_count": sum(item.item_id in deleted_event_ids for item in raw.items),
                        "assisted_deleted_evidence_count": sum(item.item_id in deleted_event_ids for item in assisted),
                    }
                )
                continue
            rows = execute_property(
                provider_name=provider_name,
                pack=pack,
                selected=selected_query,
                raw_items=raw.items,
                scorer=scorer,
                gateways=gateways,
                replicates=3,
                token_budget=2048,
                deleted_event_ids=deleted_event_ids,
            )
            if selected_query.property_name in ("authority", "provenance"):
                validate_ablation_grid(rows, required_conditions=("M0P0", "M1P0", "M0P1", "M1P1"))
            attempts.extend(rows)

        _write_jsonl(run_dir / "attempts.jsonl", attempts)
        _write_jsonl(run_dir / "retrieval-observations.jsonl", retrieval_rows)
        _write_jsonl(run_dir / "deletion-attribution.jsonl", deletion_rows)
        manifest.update(
            {
                "status": "completed",
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "provider_stats": provider.stats(),
                "ingestion": {"upserts": len(upserts), "ingested": ingest.ingested, "delete_events": delete_outcomes},
                "state_hash": baseline.state_hash,
                "attempt_rows": len(attempts),
                "retrieval_rows": len(retrieval_rows),
                "deletion_rows": len(deletion_rows),
                "reader_errors": sum(bool(row.get("reader_error")) for row in attempts),
                "temporal_status": "descriptive-application-timestamp-required" if provider_name == "hindsight" else "paired",
                "ledger": _ledger_summary(ledger_path),
            }
        )
        _write_json(manifest_path, manifest)
        (run_dir / "manifest.sha256").write_text(sha256_file(manifest_path) + "\n", encoding="utf-8")
        return manifest
    except Exception as exc:
        manifest.update({"status": "failed", "failed_at": datetime.now(timezone.utc).isoformat(), "error": f"{type(exc).__name__}: {str(exc)[:1000]}"})
        _write_json(manifest_path, manifest)
        _write_json(run_dir / "FAILED.json", manifest)
        raise
    finally:
        if provider is not None:
            if provider_name == "hindsight":
                try:
                    provider._request("DELETE", f"/v1/default/banks/{provider.bank_id}")
                except Exception:
                    pass
            provider.cleanup()


def run_provider(provider_name: str, split: str, packs: list[str], reader_mode: str) -> dict:
    if split == "test" and _git_value("status", "--porcelain"):
        raise RuntimeError("hidden TEST requires a clean committed implementation tree")
    provider_root = RUN_ROOT / split / provider_name
    provider_root.mkdir(parents=True, exist_ok=True)
    gateways, stop_gateway, ledger_path = _gateways(reader_mode, provider_name, provider_root)
    manifests = []
    try:
        for pack in packs:
            manifests.append(run_pack(provider_name, split, pack, gateways, provider_root, ledger_path))
    finally:
        stop_gateway()
    summary = {
        "schema": "sovbench/capability-attribution-provider-summary/1",
        "provider": provider_name,
        "split": split,
        "packs": packs,
        "manifests": [{"pack": item["pack"], "status": item["status"]} for item in manifests],
        "ledger": _ledger_summary(ledger_path),
        "ledger_sha256": sha256_file(ledger_path) if ledger_path.exists() else None,
        "experiment_cost_usd": _existing_experiment_cost(),
    }
    _write_json(provider_root / "summary.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", required=True, choices=tuple(PROVIDER_COMMITS))
    parser.add_argument("--split", required=True, choices=("dev", "test"))
    parser.add_argument("--pack", action="append", choices=("pack-1", "pack-2", "pack-3"))
    parser.add_argument("--reader", choices=("offline", "deepseek"))
    args = parser.parse_args()
    reader_mode = args.reader or ("offline" if args.split == "dev" else "deepseek")
    if args.split == "test" and reader_mode != "deepseek":
        raise SystemExit("hidden TEST requires the preregistered deepseek reader")
    packs = ["dev"] if args.split == "dev" else (args.pack or ["pack-1", "pack-2", "pack-3"])
    result = run_provider(args.provider, args.split, packs, reader_mode)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
