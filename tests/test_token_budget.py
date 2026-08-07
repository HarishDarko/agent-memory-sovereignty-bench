import json
import unittest

from benchmark.providers import RetrievedItem
from benchmark.token_budget import estimate_tokens, format_evidence, truncate_to_budget


class TestTokenBudget(unittest.TestCase):
    def test_estimate(self):
        self.assertEqual(estimate_tokens(""), 0)
        self.assertEqual(estimate_tokens("a"), 1)
        self.assertGreater(estimate_tokens("word " * 100), estimate_tokens("word "))

    def test_truncate_short_text_unchanged(self):
        text, tokens, truncated = truncate_to_budget("short", 100)
        self.assertEqual(text, "short")
        self.assertFalse(truncated)

    def test_truncate_respects_budget(self):
        text, tokens, truncated = truncate_to_budget("x" * 5000, 200)
        self.assertTrue(truncated)
        self.assertLessEqual(tokens, 200)
        self.assertIn("truncated", text)

    def test_format_evidence(self):
        items = [
            RetrievedItem("ev1", "alpha fact", score=0.9),
            RetrievedItem("ev2", "beta fact", score=None),
        ]
        bundle = format_evidence(items, budget=2048)
        self.assertEqual(bundle.item_ids, ("ev1", "ev2"))
        rows = [json.loads(line) for line in bundle.text.splitlines()]
        self.assertEqual(rows[0]["id"], "ev1")
        self.assertEqual(rows[0]["score"], 0.9)
        self.assertFalse(bundle.truncated)

    def test_format_evidence_empty(self):
        bundle = format_evidence([], budget=2048)
        self.assertEqual(bundle.tokens, 0)
        self.assertEqual(bundle.text, "")
        self.assertEqual(bundle.item_ids, ())

    def test_evidence_contains_provenance_metadata(self):
        bundle = format_evidence(
            [RetrievedItem("ev1", "alpha", 0.9, {"authority": "user_explicit", "source": "user"})],
            budget=2048,
        )
        row = json.loads(bundle.text)
        self.assertEqual(row["id"], "ev1")
        self.assertEqual(row["authority"], "user_explicit")
        self.assertEqual(row["source"], "user")

    def test_budget_reports_only_items_actually_sent(self):
        items = [
            RetrievedItem("a", "short evidence", 1.0, {"authority": "user_explicit"}),
            RetrievedItem("b", "x" * 1000, 0.5, {"authority": "external"}),
        ]
        bundle = format_evidence(items, budget=40)
        self.assertEqual(bundle.item_ids, ("a",))
        self.assertEqual(bundle.omitted_items, 1)


if __name__ == "__main__":
    unittest.main()
