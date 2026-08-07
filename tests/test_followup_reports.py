import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class FollowupReportTests(unittest.TestCase):
    def test_gbrain_report_is_additive_and_stopped_before_hidden_test(self):
        text = (ROOT / "docs/reports/gbrain-native-local-supplement.md").read_text(encoding="utf-8")
        self.assertIn("POST-FREEZE SUPPLEMENTARY GBRAIN-NATIVE LOCAL-EMBEDDING RUN", text)
        self.assertIn("Recall@5 was **0.7639**", text)
        self.assertIn("No hidden TEST supplementary GBrain-native", text)
        self.assertIn("hidden TEST was not touched", text)
        self.assertNotIn("protocol-v1 result", text.lower())

    def test_semantic_report_has_requested_sections_and_no_broad_scope(self):
        text = (ROOT / "docs/reports/semantic-memory-exit-v1.md").read_text(encoding="utf-8")
        for number in range(1, 31):
            self.assertIn(f"## {number}.", text)
        for phrase in (
            "Hindsight's pinned native export response",
            "Category A",
            "Category B",
            "PUBLISH V1 + ONE SMALL FOLLOW-UP",
            "layered approach",
            "Enterprise use",
            "No cross-system migration was justified",
            "c3007f4",
        ):
            self.assertIn(phrase, text)
        self.assertNotIn("Graphiti", text.split("## 30.", 1)[0])

    def test_reports_do_not_replace_the_frozen_task15_report(self):
        frozen = ROOT / "docs/reports/task15-native-track-research-review.md"
        self.assertTrue(frozen.exists())
        self.assertIn("Task 15", frozen.read_text(encoding="utf-8"))
