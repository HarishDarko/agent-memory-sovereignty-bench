"""Versioned schema contracts: dataset records, manifests, result bundles."""

import json
import tempfile
import unittest
from pathlib import Path

from benchmark import manifests
from benchmark.config import load_settings
from benchmark.events import load_events, load_ground_truth, load_queries
from benchmark.model_gateway import OfflineGateway
from benchmark.schema import SchemaError, validate_result_bundle
from benchmark.validation import validate_corpus
from benchmark.corpus import generate_corpus
from benchmark.events import Event, GroundTruth, Query


def _write_records(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")


class TestDatasetSchemas(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _valid_event(self):
        return {
            "event_id": "event_0001",
            "available_at": "2026-01-05T12:00:00Z",
            "principal": "user_001",
            "subject": "person_01",
            "scope": "personal",
            "authority": "user_explicit",
            "source": "user",
            "text": "A synthetic fact.",
            "kind": "fact",
            "supersedes": None,
            "valid_from": None,
            "valid_to": None,
            "operation": "upsert",
            "target_event_id": None,
        }

    def test_load_events_rejects_malformed_timestamp(self):
        record = self._valid_event()
        record["available_at"] = "yesterday-ish"
        _write_records(self.root / "events.jsonl", [record])
        with self.assertRaises(SchemaError):
            load_events(self.root / "events.jsonl")

    def test_load_events_rejects_unknown_field(self):
        record = self._valid_event()
        record["gold_answer"] = "leaked"
        _write_records(self.root / "events.jsonl", [record])
        with self.assertRaises(SchemaError):
            load_events(self.root / "events.jsonl")

    def test_load_events_rejects_invalid_operation(self):
        record = self._valid_event()
        record["operation"] = "forget-please"
        _write_records(self.root / "events.jsonl", [record])
        with self.assertRaises(SchemaError):
            load_events(self.root / "events.jsonl")

    def test_load_queries_rejects_unknown_field(self):
        _write_records(
            self.root / "queries.jsonl",
            [
                {
                    "query_id": "query_0001",
                    "question": "What is the editor?",
                    "principal": "user_001",
                    "subject": "person_01",
                    "scope": "personal",
                    "as_of": "2026-07-01T00:00:00Z",
                    "kind": "current_state",
                    "expected_answer": "leaked",
                }
            ],
        )
        with self.assertRaises(SchemaError):
            load_queries(self.root / "queries.jsonl")

    def test_load_ground_truth_rejects_non_string_answer(self):
        _write_records(
            self.root / "ground_truth.jsonl",
            [{"query_id": "query_0001", "answer": 42, "abstain": False, "gold_event_ids": [], "note": ""}],
        )
        with self.assertRaises(SchemaError):
            load_ground_truth(self.root / "ground_truth.jsonl")

    def test_semantic_gate_rejects_duplicate_future_and_incomplete_chain(self):
        events = [
            Event("dup", "2026-01-01T00:00:00Z", "user_001", "personal", "user_explicit", "u", "a", subject="person_01"),
            Event("dup", "2026-02-01T00:00:00Z", "user_001", "personal", "user_explicit", "u", "b", subject="person_01"),
            Event("future_gold", "2099-01-01T00:00:00Z", "user_001", "personal", "user_explicit", "u", "c", subject="person_01"),
            Event("chain_a", "2026-01-01T00:00:00Z", "user_001", "personal", "user_explicit", "u", "d", subject="person_01"),
        ]
        queries = [
            Query("q_future", "?", "user_001", "personal", "2026-08-01T00:00:00Z", subject="person_01"),
            Query("q_chain", "?", "user_001", "personal", "2026-08-01T00:00:00Z", "multi_hop", subject="person_01"),
        ]
        gold = {
            "q_future": GroundTruth("q_future", "c", False, ("future_gold",)),
            "q_chain": GroundTruth("q_chain", "a", False, ("chain_a",)),
        }
        result = validate_corpus(events, queries, gold)
        self.assertFalse(result.passed)
        self.assertTrue(any("duplicate event_id" in e for e in result.errors))
        self.assertTrue(any("future information" in e for e in result.errors))
        self.assertTrue(any("multi-hop" in e for e in result.errors))


class TestManifestSchema(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.settings = load_settings()

    def tearDown(self):
        self.tmp.cleanup()

    def _valid_manifest(self):
        return manifests.build_manifest(
            run_id="2026-08-01-001",
            track="controlled",
            settings=self.settings,
            provider_name="bm25-sqlite-fts",
            provider_version="0.1.0",
            provider_capabilities={"read_only_retrieval": True},
            control=False,
            corpus_digest_value="abcd",
            corpus_split="dev",
            prompt_digest_value="e" * 64,
            bench_time="2026-08-01T00:00:00Z",
            preflight={"passed": True, "results": []},
            scores=None,
            scorer_version="0.1.0",
            provider_stats={},
            status="aborted_preflight",
            status_reason="test",
            reader=OfflineGateway(self.settings).describe(),
            publication={"eligible": False, "reasons": ["test"]},
            dataset_validation={"passed": True, "errors": [], "warnings": []},
        )

    def test_write_manifest_rejects_missing_publication(self):
        manifest = self._valid_manifest()
        del manifest["publication"]
        with self.assertRaises(SchemaError):
            manifests.write_manifest(self.root / "r" / "manifest.json", manifest)

    def test_write_manifest_rejects_unknown_status(self):
        manifest = self._valid_manifest()
        manifest["status"] = "magically_done"
        with self.assertRaises(SchemaError):
            manifests.write_manifest(self.root / "r" / "manifest.json", manifest)

    def test_write_manifest_rejects_completed_without_scores(self):
        manifest = self._valid_manifest()
        manifest["status"] = "completed_plumbing"
        manifest["scores"] = None
        with self.assertRaises(SchemaError):
            manifests.write_manifest(self.root / "r" / "manifest.json", manifest)

    def test_write_manifest_accepts_runner_shaped_manifest(self):
        path = manifests.write_manifest(self.root / "r" / "manifest.json", self._valid_manifest())
        self.assertTrue(path.exists())


class TestSchemaSeparation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_query_schema_contains_no_answer_fields(self):
        schema = json.loads((Path(__file__).resolve().parent.parent / "schemas" / "query.schema.json").read_text(encoding="utf-8"))
        properties = schema["properties"]
        for forbidden in ("answer", "gold", "expected"):
            self.assertNotIn(forbidden, properties)
            self.assertNotIn(forbidden, schema["required"])

    def test_event_schema_contains_no_gold_fields(self):
        schema = json.loads((Path(__file__).resolve().parent.parent / "schemas" / "event.schema.json").read_text(encoding="utf-8"))
        properties = schema["properties"]
        self.assertNotIn("gold", properties)
        self.assertNotIn("answer", properties)
        self.assertNotIn("gold", schema["required"])
        self.assertNotIn("answer", schema["required"])

    def test_generated_corpus_records_pass_schema_gate(self):
        corpus = generate_corpus(seed=21, n_persons=8, n_noise=2)
        corpus.to_files(self.root)

    def test_result_bundle_validation(self):
        valid = {
            "bundle_version": "sovbench/result-bundle/1",
            "protocol": "protocols/v1/personal-controlled.md",
            "generated_at": "2026-08-01T00:00:00Z",
            "status": "draft",
            "runs": [{"run_id": "2026-08-01-001", "manifest_sha256": "a" * 64, "status": "completed_plumbing"}],
            "metrics": {},
            "uncertainty": {},
        }
        validate_result_bundle(valid)
        with self.assertRaises(SchemaError):
            validate_result_bundle({**valid, "status": "published_wrong"})


if __name__ == "__main__":
    unittest.main()
