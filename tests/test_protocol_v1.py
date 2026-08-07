"""Task 14: Phase 1 controlled-run orchestrator - gates, analysis, redaction."""

from __future__ import annotations

import json
import os
import unittest
from pathlib import Path

from benchmark.config import Settings

REPO_ROOT = Path(__file__).resolve().parent.parent
PROTOCOL_DIR = REPO_ROOT / "protocols" / "v1"
OPTMEM_MEMO = REPO_ROOT / ".optmem" / "memo"
HIDDEN_PACKS = REPO_ROOT / "scorer_private" / "test-v1"


def _trace_row(
    query_id: str,
    subject: str,
    kind: str,
    *,
    reader_correct: bool | None,
    abstain_correct: bool | None = None,
    chain: bool | None = None,
    gold_recall: float | None = None,
    precision: float | None = None,
    authority: bool | None = None,
    forbidden: int = 0,
    cross: int = 0,
    deleted: int = 0,
    retries: int = 0,
    latency_ms: float = 100.0,
    tokens_in: int = 500,
    tokens_out: int = 200,
) -> dict:
    return {
        "query_id": query_id,
        "subject": subject,
        "kind": kind,
        "reader": {
            "mode": "deepseek",
            "retries": retries,
            "latency_ms": latency_ms,
            "request_tokens": tokens_in,
            "response_tokens": tokens_out,
            "response_model_id": "deepseek-v4-flash",
            "request_id": f"req-{query_id}",
        },
        "score": {
            "reader_correct": reader_correct,
            "abstain_correct": abstain_correct,
            "chain_complete@5": chain,
            "gold_evidence_recall@5": gold_recall,
            "evidence_id_precision": precision,
            "authority_correct": authority,
            "forbidden_evidence": forbidden,
            "cross_principal_evidence": cross,
            "deleted_evidence": deleted,
        },
    }


class TestPackSettings(unittest.TestCase):
    def test_pack_settings_point_at_pack_and_keep_frozen_reader(self):
        import scripts.run_protocol_v1 as protocol

        base = Settings(
            gateway_mode="offline",
            model="deepseek-v4-flash",
            model_release="DeepSeek-V4-Flash-0731",
            thinking_enabled=False,
            temperature=0.0,
            token_budget=2048,
            track="controlled",
            clock_start="2026-08-01T00:00:00Z",
            run_root=REPO_ROOT / "runs" / "protocol-v1" / "optmem",
        )
        packs = protocol.pack_dirs(REPO_ROOT)
        self.assertEqual(sorted(packs), ["pack-1", "pack-2", "pack-3"])
        settings = protocol.pack_settings(base, "optmem", "pack-1", REPO_ROOT)
        self.assertEqual(settings.corpus_dir, packs["pack-1"])
        self.assertEqual(settings.gold_path, packs["pack-1"] / "ground_truth.jsonl")
        self.assertEqual(settings.gateway_mode, "offline")
        self.assertFalse(settings.thinking_enabled)
        self.assertEqual(settings.temperature, 0.0)
        self.assertEqual(settings.run_root, REPO_ROOT / "runs" / "protocol-v1" / "optmem")


class TestParticipantFactories(unittest.TestCase):
    def test_factory_mapping_covers_frozen_participants(self):
        import scripts.run_protocol_v1 as protocol

        expected = [
            "no-memory",
            "oracle",
            "random-retrieval",
            "full-context",
            "bm25-pure",
            "bm25-sqlite-fts",
            "optmem",
            "gbrain",
            "mem0",
            "hindsight",
        ]
        self.assertEqual(protocol.PARTICIPANTS, expected)
        for name in expected:
            self.assertIn(name, protocol.FACTORIES)


class TestCostGate(unittest.TestCase):
    def test_refuses_without_key(self):
        import scripts.run_protocol_v1 as protocol

        settings = Settings(gateway_mode="deepseek", api_key="", run_root=REPO_ROOT / "runs")
        with self.assertRaises(protocol.ProtocolGateError):
            protocol.check_cost_gate(settings)

    def test_key_only_passes_without_approval_gate(self):
        import scripts.run_protocol_v1 as protocol

        settings = Settings(gateway_mode="deepseek", api_key="k", run_root=REPO_ROOT / "runs")
        protocol.check_cost_gate(settings)


class TestParticipantStatus(unittest.TestCase):
    def test_invalid_invariant_is_reported_honestly(self):
        import scripts.run_protocol_v1 as protocol

        outcomes = [{"status": "invalid_invariant"}, {"status": "invalid_invariant"}]
        self.assertEqual(protocol._participant_status(outcomes, [], offline=True), "invalid_invariant")

    def test_reader_failure_is_not_hidden(self):
        import scripts.run_protocol_v1 as protocol

        outcomes = [{"status": "completed_plumbing"}, {"status": "reader_failure"}]
        self.assertEqual(protocol._participant_status(outcomes, [], offline=True), "reader_failure")

    def test_preflight_abort_wins(self):
        import scripts.run_protocol_v1 as protocol

        outcomes = [{"status": "completed_plumbing"}]
        self.assertEqual(protocol._participant_status(outcomes, ["network_egress"], offline=True), "aborted_preflight")

    def test_live_all_clean_is_publishable(self):
        import scripts.run_protocol_v1 as protocol

        outcomes = [{"status": "completed_publishable"}, {"status": "completed_publishable"}]
        self.assertEqual(protocol._participant_status(outcomes, [], offline=False), "completed_publishable")

    def test_live_controls_with_plumbing_runs_report_plumbing(self):
        import scripts.run_protocol_v1 as protocol

        outcomes = [{"status": "completed_plumbing"}, {"status": "completed_plumbing"}]
        self.assertEqual(protocol._participant_status(outcomes, [], offline=False), "completed_plumbing")


class TestResume(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = REPO_ROOT / "runs" / "protocol-v1" / "test-resume"
        self.tmp_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        import shutil

        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _write_run(self, participant: str, run_id: str, status: str) -> None:
        run_dir = self.tmp_dir / participant / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "manifest.json").write_text(
            json.dumps({"run_id": run_id, "status": status, "scores": {}}, sort_keys=True),
            encoding="utf-8",
        )

    def test_complete_participant_is_skippable(self):
        import scripts.run_protocol_v1 as protocol

        for pack in ("pack-1", "pack-2", "pack-3"):
            for rep in (1, 2, 3):
                self._write_run("oracle", f"{pack}-rep{rep}", "completed_publishable")
        self.assertTrue(protocol._participant_complete("oracle", self.tmp_dir, protocol.PACK_NAMES, 3))

    def test_offline_stub_manifests_do_not_satisfy_live_run(self):
        import scripts.run_protocol_v1 as protocol

        for pack in ("pack-1", "pack-2", "pack-3"):
            for rep in (1, 2, 3):
                self._write_run("oracle", f"{pack}-rep{rep}", "completed_plumbing")
        self.assertTrue(
            protocol._participant_complete("oracle", self.tmp_dir, protocol.PACK_NAMES, 3)
        )
        self.assertFalse(
            protocol._participant_complete(
                "oracle", self.tmp_dir, protocol.PACK_NAMES, 3, require_semantic_reader=True
            )
        )

    def test_partial_participant_is_not_skippable(self):
        import scripts.run_protocol_v1 as protocol

        self._write_run("oracle", "pack-1-rep1", "completed_publishable")
        self.assertFalse(protocol._participant_complete("oracle", self.tmp_dir, protocol.PACK_NAMES, 3))

    def test_invalid_run_is_not_skippable(self):
        import scripts.run_protocol_v1 as protocol

        for pack in ("pack-1", "pack-2", "pack-3"):
            for rep in (1, 2, 3):
                self._write_run("oracle", f"{pack}-rep{rep}", "invalid_invariant")
        self.assertFalse(protocol._participant_complete("oracle", self.tmp_dir, protocol.PACK_NAMES, 3))


class TestBlinding(unittest.TestCase):
    def test_mapping_is_deterministic_and_sorted(self):
        import scripts.run_protocol_v1 as protocol

        first = protocol.blinding_map(["mem0", "gbrain", "no-memory"])
        second = protocol.blinding_map(["mem0", "gbrain", "no-memory"])
        self.assertEqual(first, second)
        self.assertEqual(sorted(first.values()), ["P01", "P02", "P03"])


class TestAnalysis(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = REPO_ROOT / "runs" / "protocol-v1" / "test-analysis"
        self.tmp_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        import shutil

        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _write_participant(self, name: str, rows: list[dict]) -> None:
        run_dir = self.tmp_dir / name / "pack-1-rep1"
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "run_id": "pack-1-rep1",
                    "status": "completed_plumbing",
                    "reader": {"mode": "deepseek", "semantic_reader_validated": True},
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        with open(run_dir / "retrieval_trace.jsonl", "w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, sort_keys=True) + "\n")

    def _write_manifest(self, name: str, run_id: str, mode: str, status: str) -> None:
        run_dir = self.tmp_dir / name / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "manifest.json").write_text(
            json.dumps(
                {"run_id": run_id, "status": status, "reader": {"mode": mode}},
                sort_keys=True,
            ),
            encoding="utf-8",
        )

    def test_aggregate_computes_matrix_reliability_and_operational(self):
        import scripts.run_protocol_v1 as protocol

        rows = [
            _trace_row("q1", "s1", "current_state", reader_correct=True, abstain_correct=True, chain=True, gold_recall=1.0, precision=1.0),
            _trace_row("q1", "s1", "current_state", reader_correct=True, abstain_correct=True, chain=True, gold_recall=1.0, precision=1.0),
            _trace_row("q2", "s2", "abstention", reader_correct=False, abstain_correct=False, chain=None, gold_recall=0.0, precision=0.0, forbidden=1),
        ]
        self._write_participant("bm25-pure", rows)
        agg = protocol.aggregate_participant("bm25-pure", run_root=self.tmp_dir)
        self.assertEqual(agg["attempts"], 3)
        self.assertAlmostEqual(agg["matrix"]["reader_accuracy"], round(2 / 3, 4))
        self.assertEqual(agg["matrix"]["chain_complete@5"], 1.0)
        self.assertAlmostEqual(agg["matrix"]["abstain_accuracy"], round(2 / 3, 4))
        self.assertEqual(agg["matrix"]["forbidden_evidence_total"], 1)
        self.assertEqual(agg["reliability"]["pass_at_1"], 0.5)
        self.assertEqual(agg["reliability"]["all_success_rate"], 0.5)
        self.assertEqual(agg["operational"]["mean_latency_ms"], 100.0)
        self.assertEqual(agg["operational"]["mean_tokens"], 700.0)
        self.assertEqual(agg["reader_error_attempts"], 0)

    def test_reader_errors_are_counted(self):
        import scripts.run_protocol_v1 as protocol

        rows = [_trace_row("q1", "s1", "current_state", reader_correct=True, retries=3)]
        self._write_participant("no-memory", rows)
        agg = protocol.aggregate_participant("no-memory", run_root=self.tmp_dir)
        self.assertEqual(agg["reader_error_attempts"], 1)

    def test_pair_comparison_labels_resolved_and_unresolved(self):
        import scripts.run_protocol_v1 as protocol

        # a beats b on every query: resolved difference.
        rows_a = [
            _trace_row("q1", "s1", "current_state", reader_correct=True),
            _trace_row("q2", "s2", "current_state", reader_correct=True),
            _trace_row("q3", "s3", "current_state", reader_correct=True),
            _trace_row("q4", "s4", "current_state", reader_correct=True),
            _trace_row("q5", "s5", "current_state", reader_correct=True),
            _trace_row("q6", "s6", "current_state", reader_correct=True),
        ]
        rows_b = [
            _trace_row("q1", "s1", "current_state", reader_correct=False),
            _trace_row("q2", "s2", "current_state", reader_correct=False),
            _trace_row("q3", "s3", "current_state", reader_correct=False),
            _trace_row("q4", "s4", "current_state", reader_correct=False),
            _trace_row("q5", "s5", "current_state", reader_correct=False),
            _trace_row("q6", "s6", "current_state", reader_correct=False),
        ]
        self._write_participant("oracle", rows_a)
        self._write_participant("random-retrieval", rows_b)
        comparison = protocol.pair_compare(
            "reader_accuracy", "oracle", "random-retrieval", run_root=self.tmp_dir
        )
        self.assertEqual(comparison["label"], "resolved")
        self.assertGreater(comparison["observed_mean_diff"], 0.9)
        # Identical participants: unresolved (no evidence of difference).
        self._write_participant("oracle-copy", rows_a)
        tied = protocol.pair_compare("reader_accuracy", "oracle", "oracle-copy", run_root=self.tmp_dir)
        self.assertIn(tied["label"], ("unresolved", "invalid"))
        self.assertEqual(tied["observed_mean_diff"], 0.0)

    def test_report_redaction_blocks_private_content(self):
        import scripts.run_protocol_v1 as protocol

        pack_dir = REPO_ROOT / "scorer_private" / "test-v1" / "pack-1"
        if not pack_dir.exists():
            self.skipTest("hidden TEST packs not present")
        query_text = ""
        with open(pack_dir / "queries.jsonl", encoding="utf-8") as handle:
            query_text = json.loads(handle.readline())["question"]
        gold_answer = ""
        with open(pack_dir / "ground_truth.jsonl", encoding="utf-8") as handle:
            gold_answer = str(json.loads(handle.readline())["answer"])
        violations = protocol.redaction_violations(
            f"path scorer_private/test-v1 question {query_text} answer {gold_answer}",
            pack_dir,
        )
        self.assertTrue(violations)
        clean = protocol.redaction_violations("metric matrix only, no private content", pack_dir)
        self.assertEqual(clean, [])

    def test_report_shape_and_attempt_accounting(self):
        import scripts.run_protocol_v1 as protocol

        self._write_participant("bm25-pure", [_trace_row("q1", "s1", "current_state", reader_correct=True)])
        report = protocol.build_report(["bm25-pure"], run_root=self.tmp_dir, repo_root=REPO_ROOT)
        self.assertIn("participants", report)
        self.assertIn("comparisons", report)
        self.assertIn("freeze", report)
        accounting = report["attempts_accounting"]["bm25-pure"]
        self.assertEqual(accounting["executed"], 1)
        self.assertEqual(accounting["planned"], 64 * 3 * 3)

    def test_stale_stub_traces_in_failed_dirs_are_ignored(self):
        import scripts.run_protocol_v1 as protocol

        # A live deepseek run with real rows.
        live_rows = [_trace_row("q1", "s1", "current_state", reader_correct=True)]
        self._write_participant("bm25-pure", live_rows)
        self._write_manifest("bm25-pure", "pack-1-rep1", "deepseek", "completed_plumbing")
        # A failed dir (FAILED.json, no manifest) holding a stale stub trace.
        failed_dir = self.tmp_dir / "bm25-pure" / "pack-1-rep2"
        failed_dir.mkdir(parents=True, exist_ok=True)
        with open(failed_dir / "retrieval_trace.jsonl", "w", encoding="utf-8") as handle:
            for _ in range(64):
                handle.write(json.dumps(_trace_row("q2", "s2", "current_state", reader_correct=False), sort_keys=True) + "\n")
        (failed_dir / "FAILED.json").write_text("{}", encoding="utf-8")

        rows = protocol.load_participant_traces("bm25-pure", run_root=self.tmp_dir)
        self.assertEqual(len(rows), 1, "stale stub traces must not enter the analysis")
        agg = protocol.aggregate_participant("bm25-pure", run_root=self.tmp_dir)
        self.assertEqual(agg["matrix"]["reader_accuracy"], 1.0)
        self.assertEqual(agg["operational"]["reader_error_attempts"], 64)
        self.assertEqual(agg["attempts"], 65)


class TestQaChecks(unittest.TestCase):
    def _minimal_report(self, no_memory_matrix: dict, abstention_kind: dict | None = None) -> dict:
        import scripts.run_protocol_v1 as protocol

        report = {
            "participants": {
                "no-memory": {
                    "control": True,
                    "matrix": no_memory_matrix,
                    "by_kind": {"abstention": abstention_kind or {"abstain_accuracy": 1.0}},
                },
                "oracle": {
                    "control": True,
                    "matrix": {"recall@5": 1.0, "reader_accuracy": 1.0},
                    "by_kind": {},
                },
                "random-retrieval": {
                    "control": True,
                    "matrix": {"recall@5": 0.111},
                    "by_kind": {},
                },
            },
            "attempts_accounting": {
                "no-memory": {"executed": 576, "planned": 576},
                "oracle": {"executed": 576, "planned": 576},
                "random-retrieval": {"executed": 576, "planned": 576},
            },
            "freeze": {"verified": True},
        }
        return report

    def test_no_memory_abstaining_everywhere_passes_qa(self):
        import scripts.run_protocol_v1 as protocol

        report = self._minimal_report(
            {"abstain_rate": 1.0, "abstain_accuracy": 0.15, "recall@5": 0.0}
        )
        qa = protocol.qa_checks(report)
        self.assertTrue(qa["passed"], qa["issues"])

    def test_no_memory_answering_without_evidence_flags_leakage(self):
        import scripts.run_protocol_v1 as protocol

        report = self._minimal_report(
            {"abstain_rate": 0.9, "abstain_accuracy": 0.15, "recall@5": 0.0}
        )
        qa = protocol.qa_checks(report)
        self.assertFalse(qa["passed"])
        self.assertTrue(any("abstain rate" in issue for issue in qa["issues"]))

    def test_no_memory_missing_abstention_correctness_flags(self):
        import scripts.run_protocol_v1 as protocol

        report = self._minimal_report(
            {"abstain_rate": 1.0, "abstain_accuracy": 0.15, "recall@5": 0.0},
            abstention_kind={"abstain_accuracy": 0.8},
        )
        qa = protocol.qa_checks(report)
        self.assertFalse(qa["passed"])
        self.assertTrue(any("gold-abstention" in issue for issue in qa["issues"]))

    def test_preregistered_not_run_participants_do_not_fail_qa(self):
        import scripts.run_protocol_v1 as protocol

        report = self._minimal_report({"abstain_rate": 1.0, "abstain_accuracy": 0.15, "recall@5": 0.0})
        report["participants"]["gbrain"] = {"control": False, "matrix": {}, "by_kind": {}}
        report["attempts_accounting"]["gbrain"] = {
            "planned": 576,
            "executed": 0,
            "failed_reader_attempts": 0,
            "attributed_to_recorded_failures": 0,
        }
        report["not_run"] = [{"participant": "gbrain", "reason": "missing embedding credentials"}]
        qa = protocol.qa_checks(report)
        self.assertTrue(qa["passed"], qa["issues"])


class TestRehearsal(unittest.TestCase):
    @unittest.skipUnless(os.environ.get("SOVBENCH_RUN_PROTOCOL_REHEARSE") == "1", "env-gated rehearsal")
    def test_offline_rehearsal_on_pack_one_controls(self):
        """$0 plumbing rehearsal: controls over pack-1 with the offline stub."""
        import tempfile

        import scripts.run_protocol_v1 as protocol

        base = Settings(
            gateway_mode="offline",
            model="deepseek-v4-flash",
            prompt_path=REPO_ROOT / "prompts" / "reader-v1.md",
            prompt_version="v1",
            token_budget=2048,
            track="controlled",
            clock_start="2026-08-01T00:00:00Z",
        )
        with tempfile.TemporaryDirectory(prefix="sovbench-rehearse-") as tmp:
            run_root = Path(tmp)
            summary = protocol.run_participant(
                base,
                "no-memory",
                run_root=run_root,
                packs=["pack-1"],
                replicates=1,
                offline=True,
                repo_root=REPO_ROOT,
            )
            self.assertEqual(summary["executed_runs"], 1)
            self.assertEqual(summary["status"], "completed_plumbing")


class TestFakeUpstreamPaidPath(unittest.TestCase):
    @unittest.skipUnless(os.environ.get("SOVBENCH_RUN_PROTOCOL_FAKE") == "1", "env-gated fake-upstream run")
    def test_paid_path_with_fake_upstream(self):
        """Gate -> proxy -> ledger -> cost-state -> publishable manifest, $0."""
        import tempfile

        import scripts.run_protocol_v1 as protocol

        base = protocol._load_base(offline=False)
        base.api_key = "sk-fake-never-committed"
        upstream_url, stop = protocol._start_fake_upstream()
        import os

        os.environ["SOVBENCH_PROTOCOL_UPSTREAM_URL"] = upstream_url
        try:
            protocol.check_cost_gate(
                base, env={"SOVBENCH_DEEPSEEK_API_KEY": "sk-fake-never-committed"}
            )
            with tempfile.TemporaryDirectory(prefix="sovbench-fake-") as tmp:
                run_root = Path(tmp)
                summary = protocol.run_participant(
                    base,
                    "no-memory",
                    run_root=run_root,
                    packs=["pack-1"],
                    replicates=1,
                    offline=False,
                    repo_root=REPO_ROOT,
                )
                self.assertEqual(summary["status"], "completed_publishable")
                ledger_path = run_root / "no-memory" / "ledger.jsonl"
                self.assertTrue(ledger_path.exists())
                entries = [json.loads(line) for line in ledger_path.read_text(encoding="utf-8").splitlines() if line.strip()]
                self.assertGreater(len(entries), 0)
                self.assertEqual({e["returned_model"] for e in entries}, {"deepseek-v4-flash"})
                cost = protocol._cost_from_ledger("no-memory", run_root)
                self.assertGreater(cost["cost_usd"], 0.0)
                self.assertGreater(cost["requests"], 0)
        finally:
            stop()


class TestFactoryFailureResilience(unittest.TestCase):
    @unittest.skipUnless(HIDDEN_PACKS.exists(), "hidden TEST packs not present in this checkout")
    def test_factory_crash_records_failure_and_keeps_batch_alive(self):
        import tempfile

        import scripts.run_protocol_v1 as protocol

        original = protocol.FACTORIES["bm25-pure"]

        def boom_factory(events, gold):
            def factory(data_dir):
                if Path(data_dir).name == "data":
                    raise RuntimeError("provider construction boom")
                return original(events, gold)(data_dir)

            return factory

        protocol.FACTORIES["bm25-pure"] = boom_factory
        base = Settings(
            gateway_mode="offline",
            model="deepseek-v4-flash",
            prompt_path=REPO_ROOT / "prompts" / "reader-v1.md",
            prompt_version="v1",
            token_budget=2048,
            track="controlled",
            clock_start="2026-08-01T00:00:00Z",
        )
        try:
            with tempfile.TemporaryDirectory(prefix="sovbench-boom-") as tmp:
                summary = protocol.run_participant(
                    base,
                    "bm25-pure",
                    run_root=Path(tmp),
                    packs=["pack-1"],
                    replicates=1,
                    offline=True,
                    repo_root=REPO_ROOT,
                )
                self.assertEqual(summary["failed_runs"][0]["error_class"], "RuntimeError")
                self.assertTrue(
                    (Path(tmp) / "bm25-pure" / "pack-1-rep1" / "FAILED.json").exists()
                )
                self.assertEqual(summary["status"], "reader_failure")
        finally:
            protocol.FACTORIES["bm25-pure"] = original


class TestGBrainPartialHome(unittest.TestCase):
    def test_partial_home_is_recreated_before_git_init(self):
        import tempfile

        from providers.gbrain.adapter import GBrainProvider

        with tempfile.TemporaryDirectory(prefix="sovbench-gbrain-home-") as tmp:
            data_dir = Path(tmp)
            home = data_dir / "gbrain-home"
            brain = home / "brain"
            brain.mkdir(parents=True)
            (home / ".gbrain").mkdir()  # partial state: .gbrain without gbrain.yml
            provider = GBrainProvider.__new__(GBrainProvider)
            provider.data_dir = data_dir
            provider.home = home
            provider.brain_dir = brain
            provider._trash = []
            calls: list = []

            def fake_git(*args, **kwargs):
                calls.append(tuple(args))
                return ""

            provider._git = fake_git
            provider._git_commit = lambda *a, **k: ""
            provider._run = lambda *a, **k: ""
            provider._run_allow_failure = lambda *a, **k: (0, "")
            provider._ensure_brain()
            self.assertTrue(brain.exists(), "brain dir must exist before git init")
            self.assertTrue(any(args and args[0] == "init" for args in calls))


class TestNativeTrack(unittest.TestCase):
    @unittest.skipUnless(OPTMEM_MEMO.exists(), "pinned OptMem copy not installed in this checkout")
    def test_native_factories_wire_provider_modes(self):
        import scripts.run_protocol_v1 as protocol
        from benchmark.config import Settings

        settings = Settings(gateway_mode="deepseek", api_key="k", gateway_url="http://127.0.0.1:1")
        optmem_factory = protocol._native_factory("optmem", [], {}, settings)
        mem0_factory = protocol._native_factory("mem0", [], {}, settings)
        hindsight_factory = protocol._native_factory("hindsight", [], {}, settings)
        gbrain_factory = protocol._native_factory("gbrain", [], {}, settings)

        import tempfile

        with tempfile.TemporaryDirectory(prefix="sovbench-native-") as tmp:
            from providers.optmem.adapter import OptMemProvider

            optmem = optmem_factory(Path(tmp) / "o")
            self.assertIsInstance(optmem, OptMemProvider)
            self.assertFalse(optmem.filtering)
        with self.assertRaises(protocol.ProtocolGateError):
            gbrain_factory(Path(tmp))

    def test_gbrain_native_returns_not_run(self):
        import scripts.run_protocol_v1 as protocol
        from benchmark.config import Settings

        base = Settings(
            gateway_mode="offline",
            model="deepseek-v4-flash",
            prompt_path=REPO_ROOT / "prompts" / "reader-v1.md",
            prompt_version="v1",
            token_budget=2048,
            track="controlled",
            clock_start="2026-08-01T00:00:00Z",
        )
        import tempfile

        with tempfile.TemporaryDirectory(prefix="sovbench-native-") as tmp:
            summary = protocol.run_participant(
                base,
                "gbrain",
                run_root=Path(tmp),
                packs=["pack-1"],
                replicates=1,
                offline=True,
                repo_root=REPO_ROOT,
                native=True,
            )
            self.assertEqual(summary["status"], "not_run")
            self.assertIn("embedding provider", summary["reason"])

    def test_native_preflight_relaxes_canary_for_llm_extraction_providers(self):
        if not HIDDEN_PACKS.exists():
            self.skipTest("hidden TEST packs not present in this checkout")
        import scripts.run_protocol_v1 as protocol
        from contamination.models import PreflightResult

        canned = [
            PreflightResult("canary_isolation", False, required=True, applicable=True, details="canary failed"),
            PreflightResult("cross_user_isolation", False, required=True, applicable=True, details="leak"),
            PreflightResult("future_leakage", False, required=True, applicable=True, details="future"),
            PreflightResult("gold_inaccessibility", True, required=True, applicable=True, details="ok"),
        ]
        import contamination.preflight as preflight_module

        original = preflight_module.run_preflight
        preflight_module.run_preflight = lambda ctx, tmp: canned
        base = Settings(
            gateway_mode="offline",
            model="deepseek-v4-flash",
            prompt_path=REPO_ROOT / "prompts" / "reader-v1.md",
            prompt_version="v1",
            token_budget=2048,
            track="controlled",
            clock_start="2026-08-01T00:00:00Z",
        )
        try:
            results = protocol._preflight_for(base, "mem0", "pack-1", REPO_ROOT, native=True)
            by_check = {r.check: r for r in results}
            self.assertFalse(by_check["canary_isolation"].applicable)
            self.assertFalse(by_check["cross_user_isolation"].applicable)
            self.assertFalse(by_check["future_leakage"].applicable)
            self.assertTrue(by_check["gold_inaccessibility"].applicable)
        finally:
            preflight_module.run_preflight = original


if __name__ == "__main__":
    unittest.main()
