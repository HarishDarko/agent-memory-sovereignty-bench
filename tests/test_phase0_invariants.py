import json
import tempfile
import unittest
from pathlib import Path

from benchmark.config import Settings
from benchmark.events import Event, GroundTruth, Query, write_jsonl
from benchmark.model_gateway import ModelResponse
from benchmark.providers import AwaitResult, Capabilities, IngestResult, MemoryProvider, ProviderSnapshot, RetrievedItem, RetrievalResult
from benchmark.runner import RunConfig, run_baseline
from benchmark.scorer import Scorer
from contamination.models import PreflightResult


REPO_PROMPT = Path(__file__).resolve().parent.parent / "prompts" / "reader-v1.md"


class RecordingProvider(MemoryProvider):
    name = "recording"
    version = "test"
    capabilities = Capabilities(supports_snapshot=True, supports_restore=True, read_only_retrieval=True)

    def __init__(self, mutate_on_retrieve: bool = False):
        self.events = []
        self.ingest_batches = []
        self.ingest_calls = 0
        self.mutate_on_retrieve = mutate_on_retrieve

    def reset(self):
        self.events = []

    def ingest(self, events):
        self.events = list(events)
        self.ingest_batches.append(tuple(e.event_id for e in events))
        self.ingest_calls += 1
        return IngestResult(len(events))

    def await_ready(self, timeout_s=60.0):
        return AwaitResult(True)

    def retrieve(self, query):
        eligible = [e for e in self.events if e.available_at <= query.as_of]
        if self.mutate_on_retrieve:
            self.events.append(Event("mutation", query.as_of, query.principal, "personal", "system", "test", "mutation"))
        return RetrievalResult([RetrievedItem(e.event_id, e.text, 1.0, {"available_at": e.available_at}) for e in eligible])

    def snapshot(self):
        ids = tuple(e.event_id for e in self.events)
        return ProviderSnapshot(self.name, "|".join(ids), events=tuple(self.events))

    def restore(self, snapshot):
        self.events = list(snapshot.events)

    def stats(self):
        return {"events": len(self.events), "ingest_calls": self.ingest_calls}

    def cleanup(self):
        pass


class CountingGateway:
    mode = "offline"

    def __init__(self):
        self.calls = 0

    def describe(self):
        return {"provider": "local", "requested_model": None, "actual_model": "test-reader", "semantic_reader_validated": False}

    def generate(self, query, evidence, prompt_version):
        self.calls += 1
        return ModelResponse(
            structured={"answer": evidence[0].text if evidence else None, "abstain": not evidence, "evidence_ids": []},
            model_id="test-reader",
            mode="offline",
            prompt_hash="hash",
            request_tokens=1,
            response_tokens=1,
        )


class TestPhase0Invariants(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.corpus = self.root / "corpus"
        self.corpus.mkdir()
        self.events = [
            Event("old", "2026-02-01T00:00:00Z", "user_001", "personal", "user_explicit", "user", "old fact", subject="person_01"),
            Event("future", "2026-07-01T00:00:00Z", "user_001", "personal", "user_explicit", "user", "future fact", subject="person_01"),
        ]
        self.queries = [
            Query("q-old", "old fact?", "user_001", "personal", "2026-02-15T00:00:00Z", subject="person_01"),
            Query("q-new", "future fact?", "user_001", "personal", "2026-07-15T00:00:00Z", subject="person_01"),
        ]
        self.gold = [GroundTruth("q-old", "old fact", False, ("old",)), GroundTruth("q-new", "future fact", False, ("future",))]
        write_jsonl(self.corpus / "events.jsonl", [e.to_dict() for e in self.events])
        write_jsonl(self.corpus / "queries.jsonl", [{"query_id": q.query_id, "question": q.question, "principal": q.principal, "subject": q.subject, "scope": q.scope, "as_of": q.as_of, "kind": q.kind} for q in self.queries])
        write_jsonl(
            self.corpus / "ground_truth.jsonl",
            [{"query_id": g.query_id, "answer": g.answer, "abstain": g.abstain, "gold_event_ids": list(g.gold_event_ids), "note": ""} for g in self.gold],
        )
        self.settings = Settings(gateway_mode="offline", model="deepseek-v4-flash", prompt_path=REPO_PROMPT, corpus_dir=self.corpus, gold_path=self.corpus / "ground_truth.jsonl", run_root=self.root / "runs", report_root=self.root / "reports")

    def tearDown(self):
        self.tmp.cleanup()

    def _config(self, provider, gateway=None, preflight=None, run_id="run-1"):
        return RunConfig(run_id, provider, gateway or CountingGateway(), self.settings, Scorer(self.settings.gold_path), preflight or [PreflightResult("ok", True)])

    def test_required_preflight_failure_aborts_before_ingestion_or_scoring(self):
        provider = RecordingProvider()
        gateway = CountingGateway()
        outcome = run_baseline(self._config(provider, gateway, [PreflightResult("network_egress", False, required=True)]))
        self.assertEqual(outcome.status, "aborted_preflight")
        self.assertEqual(provider.ingest_calls, 0)
        self.assertEqual(gateway.calls, 0)
        self.assertFalse(outcome.scores_path.exists())
        manifest = json.loads(outcome.manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["status"], "aborted_preflight")
        self.assertIsNone(manifest["scores"])

    def test_each_query_checkpoint_ingests_only_events_available_at_that_time(self):
        provider = RecordingProvider()
        outcome = run_baseline(self._config(provider))
        self.assertEqual(outcome.status, "completed_plumbing")
        self.assertIn(("old",), provider.ingest_batches)
        self.assertIn(("old", "future"), provider.ingest_batches)
        traces = [json.loads(line) for line in outcome.traces_path.read_text(encoding="utf-8").splitlines()]
        old_trace = next(row for row in traces if row["query_id"] == "q-old")
        self.assertEqual(old_trace["checkpoint"]["eligible_event_ids"], ["old"])

    def test_query_mutation_invalidates_run_before_reader_or_scorer(self):
        gateway = CountingGateway()
        outcome = run_baseline(self._config(RecordingProvider(mutate_on_retrieve=True), gateway))
        self.assertEqual(outcome.status, "invalid_invariant")
        self.assertEqual(gateway.calls, 0)
        self.assertFalse(outcome.scores_path.exists())
        manifest = json.loads(outcome.manifest_path.read_text(encoding="utf-8"))
        self.assertIn("mutated", manifest["status_reason"].lower())

    def test_offline_manifest_names_actual_reader_and_is_not_publishable(self):
        outcome = run_baseline(self._config(RecordingProvider()))
        manifest = json.loads(outcome.manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["reader"]["provider"], "local")
        self.assertEqual(manifest["reader"]["actual_model"], "test-reader")
        self.assertIsNone(manifest["reader"]["requested_model"])
        self.assertFalse(manifest["publication"]["eligible"])
        self.assertFalse(manifest["reader"]["semantic_reader_validated"])


if __name__ == "__main__":
    unittest.main()
