"""Typed deterministic scoring: aliases, sets, dates, booleans, quantities,
evidence-ID precision/recall, forbidden/deleted/cross-principal evidence, and
authority choice."""

import unittest

from benchmark.events import GroundTruth, Query
from benchmark.model_gateway import ModelResponse
from benchmark.providers import RetrievedItem, RetrievalResult
from benchmark.scorer import RunScores, Scorer, aggregate_scores


def _response(answer=None, abstain=False, evidence_ids=None):
    return ModelResponse(
        structured={
            "answer": answer,
            "confidence": 1.0,
            "abstain": abstain,
            "evidence_ids": list(evidence_ids or []),
        },
        model_id="test",
        mode="offline",
        prompt_hash="h" * 64,
        request_tokens=1,
        response_tokens=1,
    )


def _query(query_id="q1", kind="current_state", principal="user_001"):
    return Query(query_id, "question?", principal, "personal", "2026-08-01T00:00:00Z", kind)


class TestTypedAnswers(unittest.TestCase):
    def _score(self, gold, query, answer, abstain=False):
        scorer = Scorer(gold={query.query_id: gold})
        return scorer.score_query(query, RetrievalResult(items=[]), _response(answer, abstain))

    def test_acceptable_aliases_are_private_and_used(self):
        gold = GroundTruth("q1", "Quill", False, ("e1",), "note", answer_type="exact", acceptable_answers=("the Quill editor",))
        self.assertTrue(self._score(gold, _query(), "the Quill editor").reader_correct)
        self.assertFalse(self._score(gold, _query(), "Slate").reader_correct)

    def test_set_answers_are_order_insensitive(self):
        gold = GroundTruth("q1", "Quill, Slate", False, ("e1",), "note", answer_type="set")
        self.assertTrue(self._score(gold, _query(), "Slate and Quill").reader_correct)
        self.assertFalse(self._score(gold, _query(), "Slate").reader_correct)

    def test_date_answers_match_aliases(self):
        gold = GroundTruth("q1", "2026-09-01", False, ("e1",), "note", answer_type="date", acceptable_answers=("September 1, 2026",))
        self.assertTrue(self._score(gold, _query(), "September 1, 2026").reader_correct)
        self.assertTrue(self._score(gold, _query(), "2026-09-01").reader_correct)
        self.assertFalse(self._score(gold, _query(), "2026-09-02").reader_correct)

    def test_boolean_answers_accept_synonyms(self):
        gold = GroundTruth("q1", "true", False, ("e1",), "note", answer_type="bool")
        self.assertTrue(self._score(gold, _query(), "Yes").reader_correct)
        self.assertFalse(self._score(gold, _query(), "No").reader_correct)

    def test_quantity_answers_ignore_formatting(self):
        gold = GroundTruth("q1", "12.50", False, ("e1",), "note", answer_type="quantity")
        self.assertTrue(self._score(gold, _query(), "$12.5").reader_correct)
        self.assertFalse(self._score(gold, _query(), "13.00").reader_correct)

    def test_abstention_still_scores(self):
        gold = GroundTruth("q1", None, True, (), "note")
        self.assertTrue(self._score(gold, _query(), None, abstain=True).reader_correct)
        self.assertFalse(self._score(gold, _query(), "guess").reader_correct)


class TestEvidenceMetrics(unittest.TestCase):
    def setUp(self):
        self.scorer = Scorer(
            gold={
                "q1": GroundTruth("q1", "Quill", False, ("e1", "e2"), "note"),
                "qa": GroundTruth("qa", "Quill", False, ("e1",), "note"),
            }
        )

    def test_evidence_id_precision_and_recall(self):
        query = _query()
        score = self.scorer.score_query(
            query,
            RetrievalResult(items=[]),
            _response("Quill", evidence_ids=["e1", "noise"]),
        )
        self.assertEqual(score.evidence_precision, 0.5)
        self.assertEqual(score.evidence_recall, 0.5)
        score_empty = self.scorer.score_query(query, RetrievalResult(items=[]), _response("Quill", evidence_ids=[]))
        self.assertEqual(score_empty.evidence_precision, 0.0)
        self.assertEqual(score_empty.evidence_recall, 0.0)

    def test_forbidden_cross_principal_and_deleted_evidence(self):
        query = _query()
        retrieval = RetrievalResult(
            items=[
                RetrievedItem("e1", "gold", 1.0, {"principal": "user_001", "kind": "fact"}),
                RetrievedItem("poison", "bad claim", 0.9, {"principal": "user_001", "kind": "poison_attempt"}),
                RetrievedItem("other", "leak", 0.8, {"principal": "user_002", "kind": "fact"}),
                RetrievedItem("gone", "deleted", 0.7, {"principal": "user_001", "kind": "fact"}),
            ]
        )
        score = self.scorer.score_query(
            query,
            retrieval,
            _response("Quill", evidence_ids=["e1"]),
            deleted_event_ids=frozenset({"gone"}),
        )
        self.assertEqual(score.forbidden_evidence, 1)
        self.assertEqual(score.cross_principal_evidence, 1)
        self.assertEqual(score.deleted_evidence, 1)

    def test_authority_choice_requires_authoritative_citation(self):
        query = _query(kind="authority_conflict")
        good = self.scorer.score_query(query, RetrievalResult(items=[]), _response("Quill", evidence_ids=["e1"]))
        self.assertTrue(good.authority_correct)
        bad = self.scorer.score_query(query, RetrievalResult(items=[]), _response("Quill", evidence_ids=["e1", "noise"]))
        self.assertFalse(bad.authority_correct)
        none = self.scorer.score_query(_query(), RetrievalResult(items=[]), _response("Quill", evidence_ids=["e1"]))
        self.assertIsNone(none.authority_correct)


class TestAggregation(unittest.TestCase):
    def test_aggregate_typed_metrics_and_deprecated_presence(self):
        query = _query()
        scorer = Scorer(gold={"q1": GroundTruth("q1", "Quill", False, ("e1",), "note")})
        score = scorer.score_query(query, RetrievalResult(items=[]), _response("Quill", evidence_ids=["e1"]))
        agg = aggregate_scores([score])
        self.assertEqual(agg.evidence_precision, 1.0)
        self.assertEqual(agg.evidence_recall, 1.0)
        self.assertEqual(agg.forbidden_evidence_total, 0)
        rendered = agg.to_dict()
        self.assertIn("deprecated_metrics", rendered)
        self.assertIn("presence_accuracy", rendered["deprecated_metrics"])
        self.assertIn("retrieved_contains_gold", score.to_dict())
        self.assertIsInstance(RunScores(), RunScores)


if __name__ == "__main__":
    unittest.main()
