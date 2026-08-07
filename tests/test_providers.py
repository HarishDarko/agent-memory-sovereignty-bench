import tempfile
import unittest
from pathlib import Path

from benchmark.corpus import generate_corpus
from benchmark.events import Event, Query
from providers.bm25 import PureBm25Provider, SqliteFtsProvider
from providers.no_memory import NoMemoryProvider
from providers.oracle import build_oracle


def _small_corpus():
    return generate_corpus(seed=7, n_persons=8, n_noise=2)


class TestNoMemory(unittest.TestCase):
    def test_empty_retrieval(self):
        provider = NoMemoryProvider()
        provider.ingest(_small_corpus().events)
        res = provider.retrieve(Query("q", "anything?", "person_01", "personal", "2026-08-01T00:00:00Z"))
        self.assertEqual(res.items, [])


class TestOracle(unittest.TestCase):
    def test_returns_gold_evidence(self):
        corpus = _small_corpus()
        provider = build_oracle(corpus.events, corpus.gold)
        q = next(q for q in corpus.queries if q.query_id in corpus.gold and corpus.gold[q.query_id].gold_event_ids)
        res = provider.retrieve(q)
        gold_ids = set(corpus.gold[q.query_id].gold_event_ids)
        self.assertTrue(res.items)
        self.assertTrue(all(it.item_id in gold_ids for it in res.items))


class TestSqliteFts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.provider = SqliteFtsProvider(Path(self.tmp.name), k=10)

    def tearDown(self):
        self.tmp.cleanup()

    def test_ingest_and_retrieve_exact(self):
        corpus = _small_corpus()
        self.provider.ingest(corpus.events)
        q = Query("q", "What is Maren Vale's preferred editor?", "user_001", "personal", "2026-08-01T00:00:00Z", subject="person_01")
        res = self.provider.retrieve(q)
        self.assertTrue(res.items, "expected at least one retrieved item")
        self.assertTrue(any("editor" in it.text.lower() for it in res.items))

    def test_principal_scoping(self):
        corpus = _small_corpus()
        self.provider.ingest(corpus.events)
        q = Query("q", "What is Ayla Brenner's preferred editor?", "user_002", "personal", "2026-08-01T00:00:00Z", subject="person_05")
        res = self.provider.retrieve(q)
        self.assertFalse(any("ayla" in it.text.lower() for it in res.items))

    def test_as_of_filter_excludes_future(self):
        events = [
            Event("past", "2026-01-01T00:00:00Z", "person_01", "personal", "user_explicit", "s", "past secret PAST-1"),
            Event("future", "2026-12-01T00:00:00Z", "person_01", "personal", "user_explicit", "s", "future secret FUTURE-1"),
        ]
        self.provider.ingest(events)
        q = Query("q", "What is the future secret?", "person_01", "personal", "2026-08-01T00:00:00Z")
        res = self.provider.retrieve(q)
        self.assertFalse(any("FUTURE-1" in it.text for it in res.items))

    def test_snapshot_restore_roundtrip(self):
        corpus = _small_corpus()
        self.provider.ingest(corpus.events)
        snap = self.provider.snapshot()
        self.provider.restore(snap)
        q = Query("q", "What is Maren Vale's preferred editor?", "user_001", "personal", "2026-08-01T00:00:00Z", subject="person_01")
        ids_a = [it.item_id for it in self.provider.retrieve(q).items]
        self.provider.restore(snap)
        ids_b = [it.item_id for it in self.provider.retrieve(q).items]
        self.assertEqual(ids_a, ids_b)

    def test_delete_removes_event_from_index_and_snapshot(self):
        event = Event(
            "secret",
            "2026-01-01T00:00:00Z",
            "user_001",
            "personal",
            "user_explicit",
            "user",
            "The deletion canary is ERASE-991.",
            subject="person_01",
        )
        self.provider.ingest([event])
        self.assertTrue(self.provider.delete("secret"))
        result = self.provider.retrieve(
            Query("q", "What is the deletion canary?", "user_001", "personal", "2026-08-01T00:00:00Z")
        )
        self.assertFalse(any(item.item_id == "secret" for item in result.items))
        self.assertNotIn("secret", {stored.event_id for stored in self.provider.snapshot().events})


class TestPureBm25(unittest.TestCase):
    def test_retrieves_relevant(self):
        with tempfile.TemporaryDirectory() as tmp:
            provider = PureBm25Provider(Path(tmp), k=10)
            corpus = _small_corpus()
            provider.ingest(corpus.events)
            q = Query("q", "What is Maren Vale's preferred editor?", "user_001", "personal", "2026-08-01T00:00:00Z", subject="person_01")
            res = provider.retrieve(q)
            self.assertTrue(res.items)


if __name__ == "__main__":
    unittest.main()
