"""Baseline parity and the random-retrieval negative control."""

import tempfile
import unittest
from pathlib import Path

from benchmark.corpus import generate_corpus
from benchmark.events import Query
from providers.bm25 import SqliteFtsProvider
from providers.full_context import FullContextProvider
from providers.random_retrieval import RandomRetrievalProvider


def _eligible_ids(corpus, query):
    return {
        event.event_id
        for event in corpus.events
        if event.available_at <= query.as_of
        and event.principal == query.principal
        and (not query.scope or event.scope == query.scope)
    }


class TestEligibleParity(unittest.TestCase):
    def test_sqlite_and_full_context_share_eligible_source_state(self):
        corpus = generate_corpus(seed=7, n_persons=8, n_noise=2)
        with tempfile.TemporaryDirectory() as tmp:
            sqlite = SqliteFtsProvider(Path(tmp) / "s", k=10)
            sqlite.ingest(corpus.events)
            full = FullContextProvider(Path(tmp) / "f")
            full.ingest(corpus.events)
            for query in corpus.queries[:12]:
                eligible = _eligible_ids(corpus, query)
                full_ids = {item.item_id for item in full.retrieve(query).items}
                sqlite_ids = {item.item_id for item in sqlite.retrieve(query).items}
                self.assertEqual(full_ids, eligible)
                self.assertTrue(sqlite_ids.issubset(full_ids), query.query_id)


class TestRandomNegativeControl(unittest.TestCase):
    def test_deterministic_and_bounded(self):
        corpus = generate_corpus(seed=9, n_persons=8, n_noise=2)
        with tempfile.TemporaryDirectory() as tmp:
            first = RandomRetrievalProvider(Path(tmp), k=10, seed=123)
            second = RandomRetrievalProvider(Path(tmp), k=10, seed=123)
            for provider in (first, second):
                provider.ingest(corpus.events)
            query = Query("q1", "What is Maren Vale's preferred editor?", "user_001", "personal", "2026-08-01T00:00:00Z")
            ids_a = [item.item_id for item in first.retrieve(query).items]
            ids_b = [item.item_id for item in second.retrieve(query).items]
            self.assertEqual(ids_a, ids_b)
            self.assertLessEqual(len(ids_a), 10)
            eligible = _eligible_ids(corpus, query)
            self.assertTrue(set(ids_a).issubset(eligible))

    def test_random_control_does_not_approach_perfect_recall(self):
        corpus = generate_corpus(seed=21, n_persons=8, n_noise=2)
        with tempfile.TemporaryDirectory() as tmp:
            provider = RandomRetrievalProvider(Path(tmp), k=10, seed=123)
            provider.ingest(corpus.events)
            scores = []
            for query in corpus.queries:
                result = provider.retrieve(query)
                ids = [item.item_id for item in result.items[:5]]
                gold = corpus.gold[query.query_id].gold_event_ids
                if gold:
                    scores.append(len(set(ids) & set(gold)) / len(gold))
            mean_recall = sum(scores) / len(scores)
            self.assertGreater(mean_recall, 0.0)
            self.assertLess(mean_recall, 0.95)


class TestControlFlags(unittest.TestCase):
    def test_run_phase0_marks_controls_excluded_from_rankings(self):
        from scripts.run_phase0 import PROVIDERS

        flags = dict(PROVIDERS)
        self.assertTrue(flags["no-memory"])
        self.assertTrue(flags["oracle"])
        self.assertTrue(flags["random-retrieval"])
        self.assertFalse(flags["bm25-sqlite-fts"])
        self.assertFalse(flags["bm25-pure"])
        self.assertFalse(flags["full-context"])


if __name__ == "__main__":
    unittest.main()
