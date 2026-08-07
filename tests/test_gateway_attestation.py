"""Hash-chained request ledger."""

import json
import tempfile
import unittest
from pathlib import Path

from benchmark.gateway.ledger import Ledger


class TestLedger(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "ledger.jsonl"
        self.ledger = Ledger(self.path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_appends_hash_chain(self):
        first = self.ledger.append({"run_id": "r-1", "error_class": None})
        second = self.ledger.append({"run_id": "r-1", "error_class": "budget_exceeded"})
        self.assertEqual(len(first), 64)
        self.assertEqual(len(second), 64)
        self.assertNotEqual(first, second)
        self.assertEqual(self.ledger.verify(), [])

    def test_chain_links_previous_entries(self):
        first = self.ledger.append({"run_id": "r-1"})
        second = self.ledger.append({"run_id": "r-2"})
        lines = self.path.read_text(encoding="utf-8").strip().splitlines()
        first_entry = json.loads(lines[0])
        second_entry = json.loads(lines[1])
        self.assertEqual(second_entry["prev_hash"], first_entry["entry_hash"])
        self.assertEqual(first_entry["prev_hash"], "GENESIS")
        self.assertEqual(first_entry["entry_hash"], first)
        self.assertEqual(second_entry["entry_hash"], second)

    def test_verify_detects_tampering(self):
        self.ledger.append({"run_id": "r-1"})
        self.ledger.append({"run_id": "r-2"})
        lines = self.path.read_text(encoding="utf-8").splitlines()
        entry = json.loads(lines[0])
        entry["run_id"] = "tampered"
        lines[0] = json.dumps(entry, sort_keys=True)
        self.path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.assertTrue(self.ledger.verify())

    def test_ledger_never_contains_secret_or_raw_content(self):
        entry = {
            "run_id": "r-1",
            "provider_id": "p-1",
            "request_hash": "a" * 64,
            "response_hash": "b" * 64,
            "requested_model": "deepseek-v4-flash",
            "returned_model": "deepseek-v4-flash-0731",
            "request_id": "req-1",
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            "error_class": None,
        }
        self.ledger.append(entry)
        text = self.path.read_text(encoding="utf-8")
        self.assertNotIn("sk-", text)
        self.assertNotIn("api_key", text)
        self.assertNotIn("Authorization", text)
        self.assertNotIn("question + evidence", text)


if __name__ == "__main__":
    unittest.main()
