"""Retrieval-only DEV run for one provider with the offline reader ($0).

Usage:
    python scripts/run_provider_dev.py --provider optmem

Preflight + checkpoint replay + retrieval + offline reader + scoring, exactly
like a scored run but with the stub reader, so the provider's adapter can be
verified on DEV before any real reader or hidden TEST involvement.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from benchmark import manifests  # noqa: E402
from benchmark.clock import BenchmarkClock  # noqa: E402
from benchmark.config import load_settings  # noqa: E402
from benchmark.events import load_events, load_ground_truth, load_queries  # noqa: E402
from benchmark.model_gateway import get_gateway  # noqa: E402
from benchmark.runner import RunConfig, run_baseline  # noqa: E402
from benchmark.scorer import Scorer  # noqa: E402
from contamination.models import PreflightContext  # noqa: E402
from contamination.preflight import run_preflight  # noqa: E402
from providers.bm25 import PureBm25Provider, SqliteFtsProvider  # noqa: E402
from providers.full_context import FullContextProvider  # noqa: E402
from providers.gbrain.adapter import make_gbrain  # noqa: E402
from providers.mem0.adapter import make_mem0  # noqa: E402
from providers.optmem.adapter import make_optmem  # noqa: E402


def _make_hindsight_gated(data_dir):
    import os

    from providers.hindsight.adapter import make_hindsight

    if os.environ.get("SOVBENCH_RUN_HINDSIGHT") != "1":
        raise RuntimeError(
            "hindsight DEV run requires SOVBENCH_RUN_HINDSIGHT=1 and a reachable "
            "HINDSIGHT_API_URL (docker compose -f docker/providers/hindsight/docker-compose.yml up -d)"
        )
    return make_hindsight(data_dir, api_url=os.environ.get("HINDSIGHT_API_URL"))


FACTORIES = {
    "optmem": lambda data_dir: make_optmem(data_dir),
    "gbrain": lambda data_dir: make_gbrain(data_dir),
    "mem0": lambda data_dir: make_mem0(data_dir),
    "hindsight": _make_hindsight_gated,
    "bm25-sqlite-fts": lambda data_dir: SqliteFtsProvider(data_dir, k=10),
    "bm25-pure": lambda data_dir: PureBm25Provider(data_dir, k=10),
    "full-context": lambda data_dir: FullContextProvider(data_dir),
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Retrieval-only DEV run for one provider.")
    parser.add_argument("--provider", required=True, choices=sorted(FACTORIES))
    parser.add_argument("--run-root", type=Path, default=None)
    parser.add_argument(
        "--until",
        default=None,
        help="Only replay queries whose as_of <= this ISO timestamp (documented plumbing slice, "
        "e.g. before lifecycle actions for append-only providers).",
    )
    args = parser.parse_args()

    settings = load_settings()
    if args.run_root:
        settings.run_root = args.run_root
    events = load_events(settings.corpus_dir / "events.jsonl")
    queries = load_queries(settings.corpus_dir / "queries.jsonl")
    if args.until:
        queries = [query for query in queries if query.as_of <= args.until]
        print(f"DEV slice: {len(queries)} queries with as_of <= {args.until}")
    gold = load_ground_truth(settings.gold_path)
    clock = BenchmarkClock(settings.clock_start)
    run_id = manifests.next_run_id(settings.run_root, clock.now()[:10])
    data_dir = settings.run_root / f"provider-{args.provider}-data"
    factory = FACTORIES[args.provider]

    ctx = PreflightContext(
        provider_name=args.provider,
        provider_factory=factory,
        settings=settings,
        clock=clock,
        events=events,
        queries=queries,
        gold=gold,
        data_dir=data_dir,
        is_control=False,
    )
    with tempfile.TemporaryDirectory(prefix="sovbench-preflight-", ignore_cleanup_errors=True) as tmp:
        preflight = run_preflight(ctx, Path(tmp))

    provider = factory(data_dir)
    gateway = get_gateway(settings, clock=clock, log_path=settings.run_root / run_id / "gateway.log")
    outcome = run_baseline(
        RunConfig(
            run_id=run_id,
            provider=provider,
            gateway=gateway,
            settings=settings,
            scorer=Scorer(settings.gold_path),
            preflight_results=preflight,
            control=False,
            notes=f"retrieval-only DEV run: {args.provider} (offline reader, $0)",
        ),
        queries_override=queries,
    )
    print(
        f"[{args.provider}] status={outcome.status} queries={outcome.scores.total} "
        f"gold_evidence_recall@5={outcome.scores.gold_evidence_recall_at_5} "
        f"chain_complete@5={outcome.scores.chain_complete_at_5} -> {outcome.run_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
