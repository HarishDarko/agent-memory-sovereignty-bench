"""Run the post-freeze GBrain Ollama supplement in a separate run root.

This script intentionally does not import or call the V1 analysis writer. DEV
must be accepted before hidden TEST is eligible, and hidden TEST is refused if
any prior follow-up TEST manifest exists.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from benchmark.clock import BenchmarkClock  # noqa: E402
from benchmark.config import Settings, load_settings  # noqa: E402
from benchmark.events import Event, Query, corpus_digest, load_events, load_ground_truth, load_queries  # noqa: E402
from benchmark.model_gateway import get_gateway  # noqa: E402
from benchmark.runner import RunConfig, run_baseline  # noqa: E402
from benchmark.scorer import aggregate_scores, Scorer  # noqa: E402
from contamination.checks import (  # noqa: E402
    check_compose_policy,
    check_gold_inaccessibility,
    check_network_egress,
    check_no_memory_control,
    check_oracle_control,
    check_reader_statelessness,
)
from contamination.models import PreflightContext, PreflightResult  # noqa: E402
from providers.gbrain.local_ollama import GBrainOllamaProvider  # noqa: E402
from scripts.attest_gbrain_local import ATTESTATION_PATH  # noqa: E402

from scripts.run_protocol_v1 import _live_gateway  # noqa: E402


FOLLOWUP_ROOT = REPO_ROOT / "runs" / "followups" / "gbrain-native-local"
DEV_CORPUS = REPO_ROOT / "datasets" / "dev" / "personal"
# Hidden TEST packs are not distributed with AMSB. Set SOVBENCH_TEST_PACK_ROOT
# to their location when running the supplementary hidden TEST (for example
# the frozen packs in the private research workspace). No private path is
# baked into this file.
TEST_PACK_ROOT = Path(os.environ.get("SOVBENCH_TEST_PACK_ROOT", REPO_ROOT / "scorer_private" / "test-v1"))
PACKS = ("pack-1", "pack-2", "pack-3")
DEFAULT_MODEL = "snowflake-arctic-embed:335m"
DEFAULT_OLLAMA_API = "http://127.0.0.1:4713"


def _load_attestation() -> dict:
    if not ATTESTATION_PATH.exists():
        raise RuntimeError(f"missing local environment attestation: {ATTESTATION_PATH}")
    return json.loads(ATTESTATION_PATH.read_text(encoding="utf-8"))


def _provider_factory(attestation: dict):
    model = str(attestation["ollama"]["model_response"])
    dimensions = int(attestation["ollama"]["embedding_dimensions"])
    api_root = str(attestation["ollama"]["base_url"]).rstrip("/")
    base_url = api_root + "/v1"

    def factory(data_dir: Path):
        return GBrainOllamaProvider(
            data_dir,
            embedding_model=model,
            embedding_dimensions=dimensions,
            ollama_base_url=base_url,
            gbrain_bin=os.environ.get("GBRAIN_BIN", "gbrain"),
            bun_bin=os.environ.get("BUN_BIN", "bun"),
        )

    return factory


def _corpus(split: str, pack: str | None = None) -> tuple[Path, Path, Path]:
    if split == "dev":
        root = DEV_CORPUS
    else:
        if pack is None:
            raise ValueError("test split requires a pack")
        root = TEST_PACK_ROOT / pack
    return root / "events.jsonl", root / "queries.jsonl", root / "ground_truth.jsonl"


def _settings(base: Settings, split: str, run_root: Path, event_path: Path, gold_path: Path) -> Settings:
    return replace(
        base,
        corpus_dir=event_path.parent,
        gold_path=gold_path,
        run_root=run_root,
        gateway_mode="deepseek",
        track="post-freeze-native-local",
        clock_start="2026-08-01T00:00:00Z",
        timeout_s=float(os.environ.get("SOVBENCH_TIMEOUT_S", "600")),
    )


def _optimized_preflight(settings: Settings, factory, pack_root: Path, gateway) -> list:
    """Run the required checks with one isolated GBrain initialization.

    The generic preflight constructs a fresh provider for every stateful check.
    That is appropriate for cheap providers but multiplies GBrain's schema
    migration startup. This local-only supplement keeps the same named
    canary, cross-user, future, mutation, fresh-state, gold, network, reader,
    no-memory, oracle, and compose assertions while reusing one clean brain.
    V1 never calls this optimized path.
    """
    events = load_events(pack_root / "events.jsonl")
    queries = load_queries(pack_root / "queries.jsonl")
    gold = load_ground_truth(pack_root / "ground_truth.jsonl")
    context = PreflightContext(
        provider_name="gbrain-native-local",
        provider_factory=factory,
        settings=settings,
        clock=BenchmarkClock(settings.clock_start),
        events=events,
        queries=queries,
        gold=gold,
        data_dir=settings.run_root / "preflight-data",
        is_control=False,
        gateway=gateway,
    )
    results = [
        check_network_egress(context),
        check_compose_policy(context),
        check_gold_inaccessibility(context),
        check_no_memory_control(context, settings.run_root / "preflight-no-memory"),
        check_oracle_control(context),
    ]
    provider = factory(settings.run_root / f"preflight-provider-{os.getpid()}")
    try:
        now = context.clock.now()
        empty = provider.snapshot()
        results.append(
            PreflightResult(
                "fresh_state",
                not empty.events,
                details="single isolated GBrain instance starts empty" if not empty.events else "provider was not empty at startup",
            )
        )
        probe_events = [
            Event(
                "canary-0", now, "p_canary", "personal", "user_explicit", "preflight",
                "Canary marker SOVBENCH-CANARY-GRAIN belongs to this provider run.", kind="canary",
            ),
            Event(
                "xu-a", now, "person_a", "personal", "user_explicit", "preflight",
                "person_a private keycode is Cipher-77.", kind="secret",
            ),
            Event(
                "future-a", "2099-01-01T00:00:00Z", "person_a", "personal", "user_explicit", "preflight",
                "person_a future secret is FUTURE-99.", kind="secret",
            ),
        ]
        probe_events.extend(
            Event(
                f"qm-{index}", now, "person_a", "personal", "user_explicit", "preflight",
                f"person_a stable fact number {index} is token QM-{100 + index}.", kind="fact",
            )
            for index in range(5)
        )
        provider.ingest(probe_events)
        provider.await_ready()

        mine = provider.retrieve(
            Query("canary-mine", "What is the canary marker SOVBENCH-CANARY-GRAIN?", "p_canary", "personal", now)
        )
        foreign = []
        for token in ("SOVBENCH-CANARY-FOREIGN-A", "SOVBENCH-CANARY-FOREIGN-B"):
            foreign.extend(
                item
                for item in provider.retrieve(
                    Query("canary-foreign", f"What is the canary marker {token}?", "p_canary", "personal", now)
                ).items
                if token in item.text
            )
        own_ok = any("SOVBENCH-CANARY-GRAIN" in item.text for item in mine.items)
        results.append(
            PreflightResult(
                "canary_isolation",
                own_ok and not foreign,
                details=f"single-instance own canary retrievable={own_ok}; foreign canaries={len(foreign)}",
            )
        )

        cross = provider.retrieve(
            Query("xu-q", "What is person_a private keycode?", "person_b", "personal", now)
        )
        cross_leak = any("Cipher-77" in item.text for item in cross.items)
        results.append(
            PreflightResult(
                "cross_user_isolation",
                not cross_leak,
                details="single-instance cross-principal query returned no secret" if not cross_leak else "CROSS-USER LEAK",
            )
        )

        future = provider.retrieve(
            Query("future-q", "What is person_a future secret?", "person_a", "personal", now)
        )
        future_leak = any("FUTURE-99" in item.text for item in future.items)
        results.append(
            PreflightResult(
                "future_leakage",
                not future_leak,
                details="single-instance as-of query excluded future event" if not future_leak else "FUTURE EVENT LEAK",
            )
        )

        before = provider.snapshot()
        provider.retrieve(Query("qm-q", "What is person_a stable fact number 3?", "person_a", "personal", now))
        after = provider.snapshot()
        mutation_ok = before.state_hash == after.state_hash
        results.append(
            PreflightResult(
                "query_mutation",
                mutation_ok,
                details="state unchanged after retrieval" if mutation_ok else "STATE MUTATED by retrieval",
            )
        )
        results.append(check_reader_statelessness(context))
    finally:
        provider.cleanup()
    failed = [r for r in results if r.required and r.applicable and not r.passed]
    if failed:
        raise RuntimeError("GBrain local preflight failed: " + "; ".join(f"{r.check}: {r.details}" for r in failed))
    return results


def _score_summary(run_dirs: list[Path]) -> dict:
    score_rows = []
    for run_dir in run_dirs:
        path = run_dir / "scores.json"
        if path.exists():
            score_rows.append(json.loads(path.read_text(encoding="utf-8")))
    metrics = (
        "recall@1",
        "recall@5",
        "recall@10",
        "gold_evidence_recall@5",
        "evidence_id_precision",
        "evidence_id_recall",
        "reader_accuracy",
        "abstain_accuracy",
        "mean_latency_ms",
    )
    summary = {metric: _mean([row.get(metric) for row in score_rows]) for metric in metrics}
    summary["runs"] = len(score_rows)
    summary["attempts"] = sum(int(row.get("total", 0)) for row in score_rows)
    summary["forbidden_evidence_total"] = sum(int(row.get("forbidden_evidence_total", 0)) for row in score_rows)
    summary["cross_principal_evidence_total"] = sum(int(row.get("cross_principal_evidence_total", 0)) for row in score_rows)
    summary["deleted_evidence_total"] = sum(int(row.get("deleted_evidence_total", 0)) for row in score_rows)
    return summary


def _mean(values: list) -> float | None:
    numeric = [float(value) for value in values if isinstance(value, (int, float))]
    return round(sum(numeric) / len(numeric), 4) if numeric else None


def _run_one(
    *,
    base: Settings,
    factory,
    preflight: list,
    split: str,
    pack: str,
    replicate: int,
    root: Path,
    gateway_url: str,
) -> Path:
    event_path, query_path, gold_path = _corpus(split, pack if split == "test" else None)
    run_dir = root / split / pack / f"rep-{replicate}"
    run_root = run_dir
    run_root.mkdir(parents=True, exist_ok=True)
    settings = _settings(base, split, run_root, event_path, gold_path)
    settings = replace(
        settings,
        gateway_url=gateway_url,
        identity_run_id=f"gbrain-native-local/{split}/{pack}/rep-{replicate}",
        identity_provider_id="gbrain-native-local",
    )
    provider = factory(run_dir / "data")
    gateway = get_gateway(settings, clock=BenchmarkClock(settings.clock_start), log_path=run_dir / "gateway.log")
    config = RunConfig(
        run_id="run",
        provider=provider,
        gateway=gateway,
        settings=settings,
        scorer=Scorer(gold_path),
        preflight_results=preflight,
        control=False,
        incremental=True,
        notes=(
            "POST-FREEZE SUPPLEMENTARY GBRAIN-NATIVE LOCAL-EMBEDDING RUN; "
            f"split={split}; pack={pack}; replicate={replicate}; "
            "incremental checkpoint ingestion reuses verified state; "
            "V1 results are not modified or merged"
        ),
    )
    outcome = run_baseline(config)
    if outcome.status not in {"completed_publishable", "completed_plumbing"}:
        raise RuntimeError(f"follow-up run failed: {outcome.status} {outcome.status_reason}")
    return run_dir / "run"


def run_split(split: str, *, force: bool = False, replicates: int = 3) -> dict:
    if split not in {"dev", "test"}:
        raise ValueError(split)
    attestation = _load_attestation()
    if not attestation.get("embedding_is_local") or attestation.get("reader_is_local"):
        raise RuntimeError("invalid model separation in environment attestation")
    base = load_settings()
    base.api_key = os.environ.get("SOVBENCH_DEEPSEEK_API_KEY", base.api_key)
    if not base.api_key:
        raise RuntimeError("SOVBENCH_DEEPSEEK_API_KEY is required for the common reader")
    factory = _provider_factory(attestation)
    artifact_root = FOLLOWUP_ROOT
    root = (
        artifact_root
        if split == "test"
        else artifact_root / f"dev-attempt-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    )
    if split == "test" and not force:
        dev_path = root / "dev-analysis.json"
        if not dev_path.exists() or not json.loads(dev_path.read_text(encoding="utf-8")).get("accepted"):
            raise RuntimeError("hidden TEST is blocked until DEV analysis has accepted=true")
        existing = list((root / "test").glob("**/manifest.json")) if (root / "test").exists() else []
        if existing:
            raise RuntimeError("hidden TEST follow-up artifacts already exist; refusing a second run")
    first_pack = "dev" if split == "dev" else PACKS[0]
    event_path, _, gold_path = _corpus(split, first_pack if split == "test" else None)
    settings = _settings(base, split, root, event_path, gold_path)
    stop_proxy = None
    try:
        gateway_url, stop_proxy = _live_gateway(
            settings,
            "gbrain-native-local",
            root / f"{split}-ledger.jsonl",
            base.api_key,
            require_identity=True,
        )
        probe_settings = replace(
            settings,
            gateway_url=gateway_url,
            identity_run_id="gbrain-native-local/preflight",
            identity_provider_id="gbrain-native-local",
        )
        probe_gateway = get_gateway(
            probe_settings,
            clock=BenchmarkClock(settings.clock_start),
            log_path=root / f"{split}-preflight-gateway.log",
        )
        preflight = _optimized_preflight(settings, factory, event_path.parent, probe_gateway)
        run_dirs = []
        if split == "dev":
            run_dirs.append(
                _run_one(
                    base=base,
                    factory=factory,
                    preflight=preflight,
                    split=split,
                    pack="dev",
                    replicate=1,
                    root=root,
                    gateway_url=gateway_url,
                )
            )
        else:
            for pack in PACKS:
                for replicate in range(1, replicates + 1):
                    run_dirs.append(
                        _run_one(
                            base=base,
                            factory=factory,
                            preflight=preflight,
                            split=split,
                            pack=pack,
                            replicate=replicate,
                            root=root,
                            gateway_url=gateway_url,
                        )
                    )
    finally:
        if stop_proxy is not None:
            stop_proxy()
    summary = _score_summary(run_dirs)
    result = {
        "schema": "sovbench/gbrain-native-local-followup/1",
        "label": "POST-FREEZE SUPPLEMENTARY GBRAIN-NATIVE LOCAL-EMBEDDING RUN",
        "split": split,
        "accepted": split == "dev" and (summary.get("recall@5") or 0.0) >= 0.85,
        "decision_rule": {
            "recall_at_5_guardrail": 0.85,
            "requires_preflight_pass": True,
            "requires_semantic_retrieval": True,
        },
        "attestation": attestation,
        "dataset": {
            "corpus_digest": corpus_digest(event_path, _corpus(split, first_pack if split == "test" else None)[1], gold_path),
            "source": str(event_path.parent),
        },
        "preflight": {"passed": True, "results": [item.to_dict() for item in preflight]},
        "summary": summary,
        "run_directories": [str(path) for path in run_dirs],
        "v1_immutable": True,
    }
    output = artifact_root / ("dev-analysis.json" if split == "dev" else "test-analysis.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=("dev", "test"), required=True)
    parser.add_argument("--force", action="store_true", help="only for controlled DEV reruns; never use for hidden TEST")
    parser.add_argument("--replicates", type=int, default=3)
    args = parser.parse_args(argv)
    if args.split == "test" and args.force:
        raise SystemExit("refusing --force for hidden TEST; the supplementary run is exactly once")
    run_split(args.split, force=args.force, replicates=args.replicates)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
