import json
import unittest
from pathlib import Path

from benchmark.events import load_events, load_queries
from benchmark.hashing import sha256_file


ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "datasets" / "followups" / "semantic-exit-v1"
GOLD = ROOT / "scorer_private" / "semantic-exit-v1" / "gold.json"


class SemanticExitDatasetTests(unittest.TestCase):
    def test_public_corpus_is_schema_valid_and_covers_required_semantics(self):
        events = load_events(DATASET / "events.jsonl")
        queries = load_queries(DATASET / "queries.jsonl")
        self.assertEqual(len(events), 24)
        self.assertEqual(len(queries), 10)
        self.assertEqual(len({event.event_id for event in events}), 24)
        kinds = {event.kind for event in events}
        required = {
            "stable_explicit_fact", "explicit_preference", "changed_preference",
            "historical_fact", "superseded_fact", "correction", "temporary_fact",
            "source_timestamp", "event_time_differs_from_ingestion",
            "explicit_user_statement", "assistant_model_inference",
            "external_untrusted_claim", "authoritative_source", "conflicting_authority",
            "private_principal_memory", "shared_group_memory", "explicit_deletion_request",
            "do_not_store_instruction", "native_model_derived_memory",
            "multi_fact_source_event", "provenance_chain", "ambiguous_claim",
        }
        self.assertTrue(required.issubset(kinds), sorted(required - kinds))
        self.assertIn("alice", {event.principal for event in events})
        self.assertIn("bob", {event.principal for event in events})
        self.assertIn("team:atlas", {event.scope for event in events})
        self.assertNotEqual(events[7].available_at, events[7].valid_from)
        self.assertTrue(any(event.operation == "delete" for event in events))
        self.assertEqual({event.target_event_id for event in events if event.operation == "delete"}, {"exit_event_011", "exit_event_012"})

    def test_private_gold_is_separate_and_contains_semantic_properties(self):
        if not GOLD.exists():
            self.skipTest("private semantic-exit gold is excluded from the OSS distribution")
        public_text = (DATASET / "events.jsonl").read_text(encoding="utf-8") + (DATASET / "queries.jsonl").read_text(encoding="utf-8")
        gold = json.loads(GOLD.read_text(encoding="utf-8"))
        self.assertTrue(set(gold["semantic_properties"]) >= {
            "factual_content", "historical_state", "provenance", "authority",
            "explicit_user_vs_model_derived", "principal_scope", "deletion_state",
        })
        self.assertEqual(len(gold["events"]), 24)
        self.assertNotIn("gold_event_ids", public_text)
        self.assertNotIn("acceptable_answers", public_text)
        self.assertNotIn(str(GOLD.parent), str(DATASET))

    def test_dataset_commitment_is_additive_and_not_v1(self):
        commitment = ROOT / "datasets" / "commitments" / "semantic-exit-v1.json"
        self.assertTrue(commitment.exists())
        record = json.loads(commitment.read_text(encoding="utf-8"))
        self.assertEqual(record["dataset_id"], "semantic-memory-exit-v1")
        self.assertNotEqual(record.get("protocol"), "protocol-v1")
        self.assertEqual(record["events_sha256"], sha256_file(DATASET / "events.jsonl"))
        self.assertEqual(record["queries_sha256"], sha256_file(DATASET / "queries.jsonl"))
