import unittest
from pathlib import Path
import subprocess
import sys

from benchmark.capability_analysis import (
    analyze_attempts,
    blind_analysis,
    validate_test_completeness,
)


def _row(provider, pack, query_id, prop, condition, replicate, correct):
    return {
        "provider": provider,
        "pack": pack,
        "query_id": query_id,
        "property": prop,
        "kind": "authority_conflict",
        "subject": query_id,
        "block": f"{pack}:{query_id}",
        "condition": condition,
        "replicate": replicate,
        "reader_correct": correct,
        "reader_abstained": False,
        "wrong_authority_selection": int(not correct),
        "future_evidence_count": 0,
        "future_answer_leakage": 0,
        "cross_principal_evidence_count": 0,
        "unauthorized_answer": False,
        "reader_error": None,
    }


class CapabilityAnalysisTests(unittest.TestCase):
    def test_analysis_script_help_runs_from_repository_root(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [sys.executable, "-B", "scripts/analyze_capability_attribution.py", "--help"],
            cwd=root,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_completeness_fails_closed_on_missing_or_duplicate_cells(self):
        rows = []
        for replicate in (1, 2, 3):
            for condition in ("M0P0", "M1P0", "M0P1", "M1P1"):
                rows.append(_row("gbrain", "pack-1", "pack1_query_0050", "authority", condition, replicate, True))
        validate_test_completeness(
            rows,
            providers=("gbrain",),
            packs=("pack-1",),
            selected={"pack1_query_0050": "authority"},
        )
        with self.assertRaisesRegex(ValueError, "duplicate"):
            validate_test_completeness(
                rows + [dict(rows[0])],
                providers=("gbrain",),
                packs=("pack-1",),
                selected={"pack1_query_0050": "authority"},
            )
        with self.assertRaisesRegex(ValueError, "missing"):
            validate_test_completeness(
                rows[:-1],
                providers=("gbrain",),
                packs=("pack-1",),
                selected={"pack1_query_0050": "authority"},
            )

    def test_analysis_reports_primary_and_two_by_two_contrasts(self):
        rows = []
        for index in range(6):
            query_id = f"q{index}"
            for replicate in (1, 2, 3):
                rows.extend(
                    [
                        _row("gbrain", "pack-1", query_id, "authority", "M0P0", replicate, False),
                        _row("gbrain", "pack-1", query_id, "authority", "M1P0", replicate, True),
                        _row("gbrain", "pack-1", query_id, "authority", "M0P1", replicate, False),
                        _row("gbrain", "pack-1", query_id, "authority", "M1P1", replicate, True),
                    ]
                )
        result = analyze_attempts(rows, resamples=500, seed=7)
        authority = result["properties"]["authority"]["gbrain"]
        self.assertEqual(authority["primary"]["absolute_delta"], 1.0)
        self.assertEqual(authority["metadata_neutral"]["absolute_delta"], 1.0)
        self.assertEqual(authority["prompt_text_only"]["absolute_delta"], 0.0)
        self.assertTrue(authority["primary"]["material"])

    def test_blinding_replaces_condition_labels_but_not_values(self):
        value = {"condition_a": "M0P0", "condition_b": "M1P1", "absolute_delta": 0.25}
        blinded = blind_analysis(value)
        self.assertEqual(blinded["condition_a"], "CELL-A")
        self.assertEqual(blinded["condition_b"], "CELL-D")
        self.assertEqual(blinded["absolute_delta"], 0.25)


if __name__ == "__main__":
    unittest.main()
