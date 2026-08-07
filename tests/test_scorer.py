import tempfile
import unittest
from pathlib import Path

from benchmark.events import GroundTruth, Query, write_jsonl
from benchmark.model_gateway import ModelResponse
from benchmark.providers import RetrievedItem, RetrievalResult
from benchmark.scorer import Scorer, aggregate_scores


def _write_gold(tmp: Path) -> Path:
    rows = [
        {"query_id": "q1", "answer": "Quill", "abstain": False, "gold_event_ids": ["event_0002"], "note": ""},
        {"query_id": "q2", "answer": None, "abstain": True, "gold_event_ids": [], "note": "secret"},
        {"query_id": "q3", "answer": "Slate", "abstain": False, "gold_event_ids": ["event_0009"], "note": ""},
    ]
    write_jsonl(tmp / "gold.jsonl", rows)
    return tmp / "gold.jsonl"


class TestScorer(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.gold_path = _write_gold(Path(self.tmp.name))
        self.scorer = Scorer(self.gold_path)

    def tearDown(self):
        self.tmp.cleanup()

    def _response(self, answer=None, abstain=False):
        return ModelResponse(
            structured={"answer": answer, "confidence": 1.0, "abstain": abstain, "evidence_ids": []},
            model_id="stub-offline",
            mode="offline",
            prompt_hash="h" * 64,
            request_tokens=1,
            response_tokens=1,
        )

    def test_presence_and_recall(self):
        q = Query("q1", "What is the editor?", "person_01", "personal", "2026-08-01T00:00:00Z", "current_state")
        retrieval = RetrievalResult(
            items=[
                RetrievedItem("event_0002", "Maren's preferred editor is Quill.", score=0.9),
                RetrievedItem("event_0001", "noise", score=0.1),
            ]
        )
        score = self.scorer.score_query(q, retrieval, self._response(answer="quill"))
        self.assertTrue(score.retrieved_contains_gold)
        self.assertEqual(score.gold_hits, 1)
        self.assertTrue(score.recall_at_1)
        self.assertTrue(score.reader_correct)

    def test_abstain_correct(self):
        q = Query("q2", "What is the secret?", "person_01", "personal", "2026-08-01T00:00:00Z", "abstention")
        retrieval = RetrievalResult(items=[])
        score = self.scorer.score_query(q, retrieval, self._response(abstain=True))
        self.assertTrue(score.abstain_correct)
        self.assertTrue(score.reader_correct)
        self.assertIsNone(score.retrieved_contains_gold)

    def test_missing_gold_recorded(self):
        q = Query("nope", "?", "person_01", "personal", "2026-08-01T00:00:00Z", "current_state")
        score = self.scorer.score_query(q, RetrievalResult(items=[]), self._response(abstain=True))
        self.assertIn("missing ground truth", score.note)
        self.assertIn("nope", self.scorer.errors[0])

    def test_aggregate(self):
        q1 = Query("q1", "a?", "person_01", "personal", "2026-08-01T00:00:00Z", "current_state")
        q2 = Query("q2", "b?", "person_01", "personal", "2026-08-01T00:00:00Z", "abstention")
        s1 = self.scorer.score_query(
            q1,
            RetrievalResult(items=[RetrievedItem("event_0002", "Maren's preferred editor is Quill.", score=1.0)]),
            self._response(answer="Quill"),
        )
        s2 = self.scorer.score_query(q2, RetrievalResult(items=[]), self._response(abstain=True))
        agg = aggregate_scores([s1, s2])
        self.assertEqual(agg.total, 2)
        self.assertEqual(agg.abstain_accuracy, 1.0)
        self.assertEqual(agg.presence_accuracy, 1.0)
        self.assertEqual(agg.reader_accuracy, 1.0)

    def test_multi_hop_requires_the_complete_evidence_chain(self):
        scorer = Scorer(
            gold={"q-chain": GroundTruth("q-chain", "Quill", False, ("relationship", "preference"))}
        )
        query = Query("q-chain", "What does the roommate prefer?", "user_001", "personal", "2026-08-01T00:00:00Z", "multi_hop")
        partial = scorer.score_query(
            query,
            RetrievalResult(items=[RetrievedItem("preference", "The preference is Quill.", 1.0)]),
            self._response(answer="Quill"),
        )
        complete = scorer.score_query(
            query,
            RetrievalResult(
                items=[
                    RetrievedItem("relationship", "A's roommate is B.", 1.0),
                    RetrievedItem("preference", "B prefers Quill.", 0.9),
                ]
            ),
            self._response(answer="Quill"),
        )
        self.assertEqual(partial.gold_recall_at_5, 0.5)
        self.assertFalse(partial.chain_complete_at_5)
        self.assertEqual(complete.gold_recall_at_5, 1.0)
        self.assertTrue(complete.chain_complete_at_5)


if __name__ == "__main__":
    unittest.main()
