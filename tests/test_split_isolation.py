"""Split governance: commitments and DEV/TEST isolation."""

import json
import tempfile
import unittest
from pathlib import Path

from benchmark.datasets.commitment import pack_commitment, verify_pack
from benchmark.datasets.generator_v2 import generate_personal, personal_test_pack
from benchmark.validation import validate_split_isolation


class TestCommitment(unittest.TestCase):
    def test_commitment_roundtrip_and_tamper_detection(self):
        with tempfile.TemporaryDirectory() as tmp:
            pack_dir = Path(tmp) / "pack-1"
            personal_test_pack(seed=7, target=64, set_name="pack-1").to_files(pack_dir)
            commitment = pack_commitment(pack_dir)
            self.assertEqual(verify_pack(pack_dir, commitment), [])
            event_path = pack_dir / "events.jsonl"
            original = event_path.read_text(encoding="utf-8")
            event_path.write_text(original + '{"tampered": true}\n', encoding="utf-8")
            self.assertTrue(verify_pack(pack_dir, commitment))

    def test_commitment_is_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            pack_dir = Path(tmp) / "pack-1"
            personal_test_pack(seed=7, target=64, set_name="pack-1").to_files(pack_dir)
            self.assertEqual(pack_commitment(pack_dir), pack_commitment(pack_dir))


class TestSplitIsolation(unittest.TestCase):
    def test_dev_and_test_pack_are_isolated(self):
        dev = generate_personal(seed=20260805)
        pack = personal_test_pack(seed=77, target=64, set_name="pack-1")
        result = validate_split_isolation(
            dev_events=dev.events,
            dev_queries=dev.queries,
            dev_gold=dev.gold,
            test_events=pack.events,
            test_queries=pack.queries,
            test_gold=pack.gold,
        )
        self.assertTrue(result.passed, result.errors)

    def test_shared_question_with_same_answer_is_detected(self):
        dev = generate_personal(seed=20260805)
        pack = personal_test_pack(seed=77, target=64, set_name="pack-1")
        from benchmark.events import Query

        dev_query = dev.queries[0]
        leaked = Query(
            "pack1_leak_query",
            dev_query.question,
            dev_query.principal,
            dev_query.scope,
            dev_query.as_of,
            dev_query.kind,
            subject=dev_query.subject,
        )
        leaked_gold = dict(pack.gold)
        leaked_gold[leaked.query_id] = dev.gold[dev_query.query_id]
        result = validate_split_isolation(
            dev_events=dev.events,
            dev_queries=dev.queries,
            dev_gold=dev.gold,
            test_events=pack.events,
            test_queries=pack.queries + [leaked],
            test_gold=leaked_gold,
        )
        self.assertFalse(result.passed)
        self.assertTrue(any("question-answer" in error for error in result.errors))

    def test_answer_leakage_between_splits_is_detected(self):
        dev = generate_personal(seed=20260805)
        pack = personal_test_pack(seed=77, target=64, set_name="pack-1")
        dev_answer = next(row.answer for row in dev.gold.values() if row.answer)
        target = next(iter(pack.gold))
        pack.gold[target] = pack.gold[target].__class__(
            target,
            dev_answer,
            False,
            pack.gold[target].gold_event_ids,
            "leak test",
        )
        result = validate_split_isolation(
            dev_events=dev.events,
            dev_queries=dev.queries,
            dev_gold=dev.gold,
            test_events=pack.events,
            test_queries=pack.queries,
            test_gold=pack.gold,
        )
        self.assertFalse(result.passed)
        self.assertTrue(any("answer" in error for error in result.errors))


if __name__ == "__main__":
    unittest.main()
