import tempfile
import unittest
from pathlib import Path

from benchmark.hashing import hash_dir, sha256_file, sha256_text
from benchmark.snapshots import check_no_mutation
from benchmark.events import Event
from providers.bm25 import SqliteFtsProvider


def _events():
    return [
        Event("e1", "2026-01-01T00:00:00Z", "person_01", "personal", "user_explicit", "s", "alpha fact"),
        Event("e2", "2026-02-01T00:00:00Z", "person_01", "personal", "user_explicit", "s", "beta fact"),
    ]


class TestHashing(unittest.TestCase):
    def test_sha256_stable(self):
        self.assertEqual(sha256_text("hello"), sha256_text("hello"))
        self.assertNotEqual(sha256_text("hello"), sha256_text("world"))

    def test_hash_file_and_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "a.txt"
            p.write_text("data", encoding="utf-8")
            self.assertEqual(sha256_file(p), sha256_file(p))
            d1 = hash_dir(tmp)
            p.write_text("data2", encoding="utf-8")
            d2 = hash_dir(tmp)
            self.assertNotEqual(d1, d2)


class TestMutationCheck(unittest.TestCase):
    def test_detects_change(self):
        a = _fake_snapshot("abc")
        b = _fake_snapshot("abd")
        self.assertFalse(check_no_mutation(a, b).passed)
        self.assertTrue(check_no_mutation(a, _fake_snapshot("abc")).passed)

    def test_bm25_state_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            provider = SqliteFtsProvider(Path(tmp))
            provider.ingest(_events())
            before = provider.snapshot()
            self.assertNotEqual(before.state_hash, "unset")
            # retrieval must not change state
            from benchmark.events import Query

            provider.retrieve(
                Query("q", "What is alpha?", "person_01", "personal", "2026-08-01T00:00:00Z")
            )
            after = provider.snapshot()
            self.assertTrue(check_no_mutation(before, after).passed)


def _fake_snapshot(hash_value):
    from benchmark.providers import ProviderSnapshot

    return ProviderSnapshot(provider="test", state_hash=hash_value, files={})


if __name__ == "__main__":
    unittest.main()
