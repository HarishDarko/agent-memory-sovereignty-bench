import json
import tempfile
import unittest
from pathlib import Path

from benchmark import manifests
from benchmark.clock import BenchmarkClock
from benchmark.config import Settings
from benchmark.corpus import generate_corpus
from benchmark.events import load_ground_truth, load_queries
from benchmark.model_gateway import OfflineGateway
from benchmark.runner import RunConfig, run_baseline
from benchmark.scorer import Scorer
from contamination.models import PreflightContext
from contamination.preflight import run_preflight
from providers.bm25 import SqliteFtsProvider
from providers.no_memory import make_no_memory
from providers.oracle import make_oracle


REPO_PROMPT = Path(__file__).resolve().parent.parent / "prompts" / "reader-v1.md"


class TestRunner(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.corpus_dir = root / "corpus"
        corpus = generate_corpus(seed=21, n_persons=8, n_noise=2)
        corpus.to_files(self.corpus_dir)
        self.gold_path = self.corpus_dir / "ground_truth.jsonl"
        self.run_root = root / "runs"
        self.settings = Settings(
            gateway_mode="offline",
            model="deepseek-v4-flash",
            prompt_path=REPO_PROMPT,
            prompt_version="v1",
            token_budget=512,
            track="controlled",
            clock_start="2026-08-01T00:00:00Z",
            corpus_dir=self.corpus_dir,
            gold_path=self.gold_path,
            run_root=self.run_root,
            report_root=root / "reports",
        )
        self.queries = load_queries(self.corpus_dir / "queries.jsonl")

    def tearDown(self):
        self.tmp.cleanup()

    def _preflight(self, factory, name, is_control=False):
        ctx = PreflightContext(
            provider_name=name,
            provider_factory=factory,
            settings=self.settings,
            clock=BenchmarkClock(self.settings.clock_start),
            events=generate_corpus(seed=21, n_persons=8, n_noise=2).events,
            queries=self.queries,
            gold=load_ground_truth(self.gold_path),
            data_dir=self.run_root / f"{name}-data",
            is_control=is_control,
        )
        with tempfile.TemporaryDirectory(prefix="preflight-") as tmp:
            return run_preflight(ctx, Path(tmp))

    def _run(self, name, factory, control):
        preflight = self._preflight(factory, name, is_control=control)
        data_dir = self.run_root / f"{name}-data"
        run_id = manifests.next_run_id(self.run_root, "2026-08-01")
        provider = factory(data_dir)
        gateway = OfflineGateway(self.settings, log_path=self.run_root / run_id / "gateway.log")
        cfg = RunConfig(
            run_id=run_id,
            provider=provider,
            gateway=gateway,
            settings=self.settings,
            scorer=Scorer(self.gold_path),
            preflight_results=preflight,
            control=control,
        )
        return run_baseline(cfg)

    def test_no_memory_control_always_abstains(self):
        outcome = self._run("no-memory", lambda d: make_no_memory(d), control=True)
        self.assertTrue(outcome.preflight_ok)
        self.assertTrue(all(qs.reader_abstained for qs in outcome.query_scores))
        self.assertEqual(outcome.mutation_warnings, 0)

    def test_oracle_control_perfect_presence(self):
        events = generate_corpus(seed=21, n_persons=8, n_noise=2).events
        gold = load_ground_truth(self.gold_path)
        outcome = self._run("oracle", lambda d: make_oracle(events, gold, d), control=True)
        self.assertTrue(outcome.preflight_ok)
        self.assertEqual(outcome.scores.presence_accuracy, 1.0)
        self.assertEqual(outcome.mutation_warnings, 0)

    def test_bm25_baseline_run(self):
        outcome = self._run("bm25", lambda d: SqliteFtsProvider(d, k=10), control=False)
        self.assertTrue(outcome.preflight_ok)
        self.assertEqual(outcome.mutation_warnings, 0)
        self.assertGreater(outcome.scores.presence_accuracy or 0.0, 0.5)

    def test_artifacts_written(self):
        outcome = self._run("bm25", lambda d: SqliteFtsProvider(d, k=10), control=False)
        manifest = json.loads((outcome.run_dir / "manifest.json").read_text(encoding="utf-8"))
        self.assertTrue(manifest["isolation"]["passed"])
        self.assertTrue((outcome.run_dir / "scores.json").exists())
        self.assertTrue((outcome.run_dir / "run.log").exists())
        self.assertTrue((outcome.run_dir / "retrieval_trace.jsonl").exists())
        self.assertEqual(len(outcome.query_scores), len(self.queries))
        self.assertEqual(manifest["reader"]["actual_model"], "stub-offline")
        self.assertIsNone(manifest["reader"]["requested_model"])
        self.assertEqual(manifest["status"], "completed_plumbing")


class _CountingProvider:
    """Delegating wrapper that counts ingestion calls (restore re-ingests)."""

    def __init__(self, inner):
        self.inner = inner
        self.reset_calls = 0

    def __getattr__(self, name):
        return getattr(self.inner, name)

    def reset(self):
        self.reset_calls += 1
        return self.inner.reset()


class TestCheckpointStateReuse(unittest.TestCase):
    """Queries at the same checkpoint share verified state instead of
    re-ingesting per query: ingestion happens once per checkpoint, and the
    per-query baseline-hash + mutation checks keep the isolation guarantee."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.corpus_dir = root / "corpus"
        corpus = generate_corpus(seed=7, n_persons=8, n_noise=1)
        corpus.to_files(self.corpus_dir)
        self.gold_path = self.corpus_dir / "ground_truth.jsonl"
        self.run_root = root / "runs"
        self.settings = Settings(
            gateway_mode="offline",
            model="deepseek-v4-flash",
            prompt_path=REPO_PROMPT,
            prompt_version="v1",
            token_budget=512,
            track="controlled",
            clock_start="2026-08-01T00:00:00Z",
            corpus_dir=self.corpus_dir,
            gold_path=self.gold_path,
            run_root=self.run_root,
            report_root=root / "reports",
        )
        self.queries = load_queries(self.corpus_dir / "queries.jsonl")

    def tearDown(self):
        self.tmp.cleanup()

    def test_state_rebuilt_once_per_checkpoint_not_per_query(self):
        from benchmark.model_gateway import OfflineGateway
        from benchmark.runner import RunConfig, run_baseline
        from benchmark.scorer import Scorer

        inner = SqliteFtsProvider(self.run_root / "fts-data", k=10)
        provider = _CountingProvider(inner)
        outcome = run_baseline(
            RunConfig(
                run_id="reuse-1",
                provider=provider,
                gateway=OfflineGateway(self.settings),
                settings=self.settings,
                scorer=Scorer(self.gold_path),
                preflight_results=[],
                control=False,
            )
        )
        self.assertTrue(outcome.status.startswith("completed_"))
        as_ofs = {q.as_of for q in self.queries}
        self.assertEqual(
            provider.reset_calls,
            len(as_ofs),
            "state must be rebuilt once per checkpoint, not once per query",
        )

    def test_incremental_ingestion_is_state_equivalent(self):
        from benchmark.model_gateway import OfflineGateway
        from benchmark.runner import RunConfig, run_baseline
        from benchmark.scorer import Scorer

        def run(incremental: bool) -> list[dict]:
            run_id = "incr" if incremental else "reset"
            provider = SqliteFtsProvider(self.run_root / f"fts-{run_id}", k=10)
            outcome = run_baseline(
                RunConfig(
                    run_id=run_id,
                    provider=provider,
                    gateway=OfflineGateway(self.settings),
                    settings=self.settings,
                    scorer=Scorer(self.gold_path),
                    preflight_results=[],
                    control=False,
                    incremental=incremental,
                )
            )
            rows = [
                json.loads(line)
                for line in (outcome.run_dir / "retrieval_trace.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
            ]
            return [
                {
                    "query_id": row["query_id"],
                    "item_ids": row["retrieval"]["item_ids"],
                    "reader_abstained": row["reader"]["structured"]["abstain"],
                }
                for row in rows
            ]

        reset_rows = run(incremental=False)
        incremental_rows = run(incremental=True)
        self.assertEqual(len(incremental_rows), len(reset_rows))
        by_id = {row["query_id"]: row for row in reset_rows}
        for row in incremental_rows:
            self.assertEqual(
                row,
                by_id[row["query_id"]],
                f"incremental state differs from reset-full for {row['query_id']}",
            )


if __name__ == "__main__":
    unittest.main()
