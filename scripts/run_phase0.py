"""Phase 0 end-to-end: preflight + controls and baselines at $0 cost."""

from __future__ import annotations

import sys
import tempfile
import tomllib
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
from providers.no_memory import make_no_memory  # noqa: E402
from providers.oracle import make_oracle  # noqa: E402
from providers.random_retrieval import RandomRetrievalProvider  # noqa: E402


# (provider name, control flag). Controls (no-memory, oracle, random) are
# excluded from provider rankings; baselines (BM25, full-context) are not.
PROVIDERS = [
    ("no-memory", True),
    ("oracle", True),
    ("random-retrieval", True),
    ("bm25-sqlite-fts", False),
    ("bm25-pure", False),
    ("full-context", False),
]

PROVIDER_CONFIG_DIR = Path(__file__).resolve().parent.parent / "config" / "providers"


def _load_provider_config(name: str) -> dict:
    path = PROVIDER_CONFIG_DIR / f"{name}.toml"
    if not path.exists():
        return {}
    with open(path, "rb") as handle:
        return tomllib.load(handle).get("provider", {})


def _provider_factory(name: str, events, gold):
    if name == "no-memory":
        return lambda data_dir: make_no_memory(data_dir)
    if name == "oracle":
        return lambda data_dir: make_oracle(events, gold, data_dir)
    if name == "random-retrieval":
        config = _load_provider_config("random-retrieval")
        return lambda data_dir: RandomRetrievalProvider(data_dir, k=int(config.get("k", 10)), seed=int(config.get("seed", 20260805)))
    if name == "bm25-sqlite-fts":
        return lambda data_dir: SqliteFtsProvider(data_dir, k=10)
    if name == "bm25-pure":
        config = _load_provider_config("bm25-pure")
        return lambda data_dir: PureBm25Provider(
            data_dir,
            k=int(config.get("k", 10)),
            k1=float(config.get("k1", 1.5)),
            b=float(config.get("b", 0.75)),
        )
    if name == "full-context":
        config = _load_provider_config("full-context")
        return lambda data_dir: FullContextProvider(data_dir, ordering=str(config.get("ordering", "recency")))
    raise ValueError(f"unknown Phase 0 provider: {name}")


def main() -> None:
    settings = load_settings()
    events = load_events(settings.corpus_dir / "events.jsonl")
    queries = load_queries(settings.corpus_dir / "queries.jsonl")
    gold = load_ground_truth(settings.gold_path)
    clock = BenchmarkClock(settings.clock_start)
    date_str = clock.now()[:10]

    outcomes = []
    for name, control in PROVIDERS:
        factory = _provider_factory(name, events, gold)
        run_id = manifests.next_run_id(settings.run_root, date_str)
        data_dir = settings.run_root / f"phase0-{name}-data"

        ctx = PreflightContext(
            provider_name=name,
            provider_factory=factory,
            settings=settings,
            clock=clock,
            events=events,
            queries=queries,
            gold=gold,
            data_dir=data_dir,
            is_control=control,
        )
        with tempfile.TemporaryDirectory(prefix="sovbench-preflight-") as tmp:
            preflight_results = run_preflight(ctx, Path(tmp))

        provider = factory(data_dir)
        gateway = get_gateway(settings, clock=clock, log_path=settings.run_root / run_id / "gateway.log")
        scorer = Scorer(settings.gold_path)
        cfg = RunConfig(
            run_id=run_id,
            provider=provider,
            gateway=gateway,
            settings=settings,
            scorer=scorer,
            preflight_results=preflight_results,
            control=control,
            notes=f"Phase 0 baseline: {name} (offline gateway stub, $0)",
        )
        outcome = run_baseline(cfg)
        outcomes.append(outcome)
        failed = [r.check for r in preflight_results if r.required and r.applicable and not r.passed]
        not_applicable = [r.check for r in preflight_results if r.required and not r.applicable]
        print(
            f"[{name}] status={outcome.status} preflight={'PASS' if outcome.preflight_ok else 'FAIL'} "
            f"(failed={failed or 'none'}; not_applicable={not_applicable or 'none'}) | "
            f"queries={outcome.scores.total} gold_evidence_recall@5={outcome.scores.gold_evidence_recall_at_5} "
            f"chain_complete@5={outcome.scores.chain_complete_at_5} "
            f"mutation_warnings={outcome.mutation_warnings} -> {outcome.run_dir}"
        )

    summary_path = settings.report_root / "phase0-summary.md"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Phase 0 plumbing summary",
        "",
        f"clock start: {settings.clock_start}",
        "gateway mode: offline deterministic stub ($0)",
        "publication eligibility: no",
        "",
    ]
    lines.append("| run | status | queries | gold evidence recall@5 | complete chain@5 | mutations |")
    lines.append("|---|---|---:|---:|---:|---:|")
    for o in outcomes:
        s = o.scores
        lines.append(
            f"| {o.run_dir.name} | {o.status} | {s.total} | {s.gold_evidence_recall_at_5} | "
            f"{s.chain_complete_at_5} | {s.mutation_warnings} |"
        )
    lines.append("")
    lines.append("These values verify harness plumbing only. They are not memory-system benchmark results or a leaderboard.")
    summary_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nsummary: {summary_path}")


if __name__ == "__main__":
    main()
