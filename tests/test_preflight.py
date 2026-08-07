import tempfile
import unittest
from pathlib import Path

from benchmark.clock import BenchmarkClock
from benchmark.config import load_settings
from benchmark.corpus import generate_corpus
from contamination.checks import (
    check_canary_isolation,
    check_compose_policy,
    check_cross_user_isolation,
    check_future_leakage,
    check_gold_inaccessibility,
    check_network_egress,
    check_no_memory_control,
    check_oracle_control,
    check_query_mutation,
    check_fresh_state,
    check_reader_statelessness,
)
from contamination.models import PreflightContext
from contamination.preflight import run_preflight
from providers.bm25 import SqliteFtsProvider


def _context(tmp: Path, data_dir: Path):
    settings = load_settings()
    settings.clock_start = "2026-08-01T00:00:00Z"
    corpus = generate_corpus(seed=11, n_persons=8, n_noise=2)
    ctx = PreflightContext(
        provider_name="bm25-sqlite-fts",
        provider_factory=lambda d: SqliteFtsProvider(d, k=10),
        settings=settings,
        clock=BenchmarkClock(settings.clock_start),
        events=corpus.events,
        queries=corpus.queries,
        gold=corpus.gold,
        data_dir=data_dir,
    )
    return ctx


class TestPreflightChecks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.data_dir = self.root / "provider-data"
        self.ctx = _context(self.root, self.data_dir)

    def tearDown(self):
        self.tmp.cleanup()

    def test_all_checks_pass_for_bm25(self):
        results = run_preflight(self.ctx, self.root / "preflight-tmp")
        failed = [r.check for r in results if r.required and r.applicable and not r.passed]
        self.assertEqual(failed, [], f"expected all preflight checks to pass, failed: {failed}")

    def test_gold_inaccessibility_detects_overlap(self):
        result = check_gold_inaccessibility(self.ctx)
        self.assertTrue(result.passed)
        self.ctx.data_dir = Path(self.ctx.settings.gold_path).parent
        result = check_gold_inaccessibility(self.ctx)
        self.assertFalse(result.passed)

    def test_individual_checks(self):
        checks = [
            check_network_egress(self.ctx),
            check_no_memory_control(self.ctx, self.root / "t1"),
            check_oracle_control(self.ctx),
            check_canary_isolation(self.ctx, self.root / "t2"),
            check_cross_user_isolation(self.ctx, self.root / "t3"),
            check_future_leakage(self.ctx, self.root / "t4"),
            check_query_mutation(self.ctx, self.root / "t5"),
            check_fresh_state(self.ctx, self.root / "t6"),
            check_reader_statelessness(self.ctx),
            check_compose_policy(self.ctx),
        ]
        for result in checks:
            self.assertTrue(result.passed, f"{result.check}: {result.details}")

    def test_static_policy_is_not_misreported_as_runtime_egress_proof(self):
        runtime = check_network_egress(self.ctx)
        static = check_compose_policy(self.ctx)
        self.assertFalse(runtime.applicable)
        self.assertIn("in-process", runtime.details)
        self.assertTrue(static.applicable)
        self.assertTrue(static.passed)

    def test_offline_stub_does_not_claim_semantic_reader_controls(self):
        no_memory = check_no_memory_control(self.ctx, self.root / "reader")
        stateless = check_reader_statelessness(self.ctx)
        self.assertFalse(no_memory.applicable)
        self.assertFalse(stateless.applicable)
        self.assertIn("offline", no_memory.details)


class _FakeGateway:
    """Minimal gateway double: configured to abstain or leak."""

    def __init__(self, abstain: bool = True):
        self.abstain = abstain
        self.calls = 0

    def generate(self, query, evidence, prompt_version):
        self.calls += 1
        return type("Response", (), {"structured": {"abstain": self.abstain}})()


class TestSemanticNoMemoryProbe(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.ctx = _context(self.root, self.root / "provider-data")
        self.ctx.settings.gateway_mode = "deepseek"

    def tearDown(self):
        self.tmp.cleanup()

    def test_abstaining_reader_passes_probe(self):
        gateway = _FakeGateway(abstain=True)
        self.ctx.gateway = gateway
        result = check_no_memory_control(self.ctx, self.root)
        self.assertTrue(result.passed)
        self.assertEqual(gateway.calls, 5)
        self.assertEqual(result.details.split("leaked=")[1], "0")

    def test_leaking_reader_fails_probe(self):
        self.ctx.gateway = _FakeGateway(abstain=False)
        result = check_no_memory_control(self.ctx, self.root)
        self.assertFalse(result.passed)
        self.assertTrue(result.applicable)

    def test_live_mode_without_gateway_fails_closed(self):
        self.ctx.gateway = None
        result = check_no_memory_control(self.ctx, self.root)
        self.assertFalse(result.passed)
        self.assertTrue(result.required)

    def test_reader_statelessness_passes_with_gateway(self):
        self.ctx.gateway = _FakeGateway()
        result = check_reader_statelessness(self.ctx)
        self.assertTrue(result.passed)
        self.assertTrue(result.applicable)

    def test_reader_statelessness_fails_closed_without_gateway(self):
        self.ctx.gateway = None
        result = check_reader_statelessness(self.ctx)
        self.assertFalse(result.passed)


if __name__ == "__main__":
    unittest.main()
