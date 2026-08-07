import unittest

from benchmark.capability_attribution import (
    assisted_filter,
    build_test_selection,
    build_reader_conditions,
    contrast_statistics,
    exposure_metrics,
    material_effect,
    strip_governance_metadata,
    validate_ablation_grid,
)
from benchmark.events import Query
from benchmark.providers import RetrievedItem


def _item(item_id, *, principal="user_001", scope="personal", available_at="2026-06-01T00:00:00Z", authority="user_explicit"):
    return RetrievedItem(
        item_id,
        f"text for {item_id}",
        0.9,
        {
            "principal": principal,
            "scope": scope,
            "available_at": available_at,
            "authority": authority,
            "source": "user" if authority == "user_explicit" else "forum_post",
            "subject": "person_01",
            "kind": "fact" if authority == "user_explicit" else "poison_attempt",
        },
    )


class SelectionTests(unittest.TestCase):
    def test_hidden_selection_is_exactly_preregistered_and_category_based(self):
        selection = build_test_selection(["pack-1", "pack-2", "pack-3"])
        self.assertEqual(len(selection), 60)
        self.assertEqual(selection["pack1_query_0050"], "authority")
        self.assertEqual(selection["pack2_query_0056"], "provenance")
        self.assertEqual(selection["pack3_query_0059"], "scope")
        self.assertEqual(selection["pack1_query_0052"], "deletion")
        self.assertEqual(
            [qid for qid, prop in selection.items() if qid.startswith("pack2_") and prop == "temporal"],
            [f"pack2_query_{index:04d}" for index in range(1, 13)],
        )


class EvidenceAblationTests(unittest.TestCase):
    def test_metadata_ablation_preserves_ids_text_scores_order_and_input(self):
        original = [_item("a"), _item("b", authority="external")]
        stripped = strip_governance_metadata(original)
        self.assertEqual([(x.item_id, x.text, x.score) for x in stripped], [(x.item_id, x.text, x.score) for x in original])
        self.assertEqual([x.metadata for x in stripped], [{}, {}])
        self.assertIn("authority", original[0].metadata)

    def test_assisted_filter_changes_only_temporal_principal_and_scope_eligibility(self):
        query = Query("q", "question", "user_001", "personal", "2026-07-01T00:00:00Z")
        items = [
            _item("eligible"),
            _item("future", available_at="2026-08-01T00:00:00Z"),
            _item("other-user", principal="user_002"),
            _item("other-scope", scope="work"),
        ]
        filtered = assisted_filter(items, query)
        self.assertEqual([item.item_id for item in filtered], ["eligible"])
        self.assertEqual(filtered[0].metadata, items[0].metadata)

    def test_reader_conditions_share_the_assisted_budgeted_item_set(self):
        items = [_item("a"), _item("b", authority="external")]
        conditions = build_reader_conditions(items, budget=2048)
        self.assertEqual(set(conditions), {"M0P0", "M1P0", "M0P1", "M1P1"})
        expected_ids = ["a", "b"]
        for value in conditions.values():
            self.assertEqual([item.item_id for item in value], expected_ids)
        self.assertEqual(conditions["M0P0"][0].metadata, {})
        self.assertIn("authority", conditions["M1P1"][0].metadata)

    def test_exposure_metrics_use_scorer_visible_metadata_not_reader_redaction(self):
        query = Query("q", "question", "user_001", "personal", "2026-07-01T00:00:00Z")
        items = [
            _item("external", authority="external"),
            _item("future", available_at="2026-08-01T00:00:00Z"),
            _item("other", principal="user_002"),
        ]
        metrics = exposure_metrics(
            items,
            query,
            cited_ids={"external", "other"},
            reader_correct=False,
            expected_abstain=True,
            reader_abstained=False,
            deleted_event_ids={"future"},
        )
        self.assertEqual(metrics["wrong_authority_selection"], 1)
        self.assertEqual(metrics["future_evidence_count"], 1)
        self.assertEqual(metrics["cross_principal_evidence_count"], 1)
        self.assertEqual(metrics["deleted_evidence_count"], 1)
        self.assertTrue(metrics["unauthorized_answer"])


class GridValidationTests(unittest.TestCase):
    def test_incomplete_or_text_mismatched_reader_grid_is_rejected(self):
        rows = [
            {"provider": "gbrain", "pack": "pack-1", "query_id": "q", "replicate": 1, "condition": condition, "reader_item_signature": "same"}
            for condition in ("M0P0", "M1P0", "M0P1", "M1P1")
        ]
        validate_ablation_grid(rows, required_conditions=("M0P0", "M1P0", "M0P1", "M1P1"))
        rows[-1]["reader_item_signature"] = "changed"
        with self.assertRaisesRegex(ValueError, "reader item signature"):
            validate_ablation_grid(rows, required_conditions=("M0P0", "M1P0", "M0P1", "M1P1"))


class StatisticsTests(unittest.TestCase):
    def test_contrast_reuses_existing_paired_statistics_and_requires_all_materiality_gates(self):
        rows = []
        for index in range(1, 7):
            for condition, correct in (("M0P0", False), ("M1P1", True)):
                rows.append(
                    {
                        "provider": "gbrain",
                        "property": "authority",
                        "pack": "pack-1",
                        "subject": f"subject-{index}",
                        "query_id": f"q{index}",
                        "replicate": 1,
                        "condition": condition,
                        "reader_correct": correct,
                    }
                )
        stats = contrast_statistics(rows, "M0P0", "M1P1", metric="reader_correct", resamples=500, seed=7)
        self.assertEqual(stats["absolute_delta"], 1.0)
        self.assertEqual(stats["mcnemar"]["discordant"], 6)
        self.assertTrue(material_effect(stats, holm_p_value=stats["mcnemar"]["p_value"]))
        self.assertFalse(material_effect(stats, holm_p_value=0.051))


if __name__ == "__main__":
    unittest.main()
