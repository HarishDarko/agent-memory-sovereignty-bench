import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORTS = (
    ROOT / "docs/reports/semantic-memory-exit-v1-errata.md",
    ROOT / "docs/reports/semantic-memory-exit-v1-corrected.md",
    ROOT / "docs/reports/publication-readiness-review.md",
)


class SemanticExitCorrectionReportTests(unittest.TestCase):
    def test_correction_reports_exist_and_are_redacted(self):
        for report in REPORTS:
            self.assertTrue(report.exists(), report)
            text = report.read_text(encoding="utf-8")
            self.assertNotIn("SOVBENCH_DEEPSEEK_API_KEY=", text)
            self.assertNotIn("C:\\Users\\", text)

    def test_errata_identifies_all_three_corrections(self):
        text = REPORTS[0].read_text(encoding="utf-8")
        for phrase in (
            "wrong export surface",
            "recovery configuration/procedure mistake",
            "maximal documented OSS",
            "attempt-20260807T063919Z",
            "attempt-20260807T065643Z",
            "attempt-20260807T065850Z",
            "Findings explicitly retracted",
        ):
            self.assertIn(phrase, text)

    def test_corrected_report_keeps_layers_separate(self):
        text = REPORTS[1].read_text(encoding="utf-8")
        for phrase in (
            "State ownership",
            "Same-system recoverability",
            "Semantic portability",
            "Behavioral portability",
            "hindsight-admin export-bank",
            "both bounded paths",
            "get_all()+history(memory_id)",
            "Adapter-supplied",
            "No cross-system migration was implemented",
        ):
            self.assertIn(phrase, text)

    def test_publication_review_does_not_start_a_new_experiment(self):
        text = REPORTS[2].read_text(encoding="utf-8")
        self.assertIn("No additional experiment is scientifically essential", text)
        self.assertIn("IETF", text)
        self.assertIn("W3C AI Agent Memory Interoperability Community Group", text)
        self.assertNotIn("Graphiti", text)
        self.assertNotIn("Cognee", text)
        self.assertNotIn("MIND-Mem", text)

    def test_original_report_is_unchanged_from_post_freeze_record(self):
        report = ROOT / "docs/reports/semantic-memory-exit-v1.md"
        # AMSB has a fresh Git history, so the source-repo commit reference is
        # replaced by a SHA-256 recorded at extraction time; the file is
        # byte-identical to the source report (see docs/research-history/).
        recorded = (
            ROOT / "docs" / "research-history" / "original-report-sha256.txt"
        ).read_text(encoding="utf-8").strip()
        from benchmark.hashing import sha256_file

        self.assertEqual(sha256_file(report), recorded)


if __name__ == "__main__":
    unittest.main()
