"""Full-context control: no retrieval, deterministic recency order, strict filters."""

import tempfile
import unittest
from pathlib import Path

from benchmark.events import Event, Query
from providers.full_context import FullContextProvider


def _event(event_id, available_at, principal="user_001", scope="personal", kind="fact"):
    return Event(
        event_id,
        available_at,
        principal,
        scope,
        "user_explicit",
        "user",
        f"fact text {event_id}",
        kind=kind,
        subject="person_01",
    )


class TestFullContextProvider(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.provider = FullContextProvider(Path(self.tmp.name))
        self.events = [
            _event("e-past", "2026-01-01T00:00:00Z"),
            _event("e-mid", "2026-06-01T00:00:00Z"),
            _event("e-future", "2026-12-01T00:00:00Z"),
            _event("e-other-principal", "2026-03-01T00:00:00Z", principal="user_002"),
            _event("e-other-scope", "2026-04-01T00:00:00Z", scope="work"),
        ]
        self.provider.ingest(self.events)

    def tearDown(self):
        self.tmp.cleanup()

    def _query(self, as_of="2026-07-01T00:00:00Z", principal="user_001", scope="personal"):
        return Query("q1", "question?", principal, scope, as_of)

    def test_future_events_are_excluded(self):
        result = self.provider.retrieve(self._query())
        ids = {item.item_id for item in result.items}
        self.assertNotIn("e-future", ids)
        self.assertIn("e-past", ids)
        self.assertIn("e-mid", ids)

    def test_principal_and_scope_filtering(self):
        result = self.provider.retrieve(self._query())
        ids = {item.item_id for item in result.items}
        self.assertNotIn("e-other-principal", ids)
        self.assertNotIn("e-other-scope", ids)
        work = self.provider.retrieve(self._query(scope="work"))
        self.assertEqual({item.item_id for item in work.items}, {"e-other-scope"})

    def test_deleted_events_are_excluded(self):
        self.provider.delete("e-mid")
        ids = {item.item_id for item in self.provider.retrieve(self._query()).items}
        self.assertNotIn("e-mid", ids)

    def test_deterministic_recency_ordering(self):
        first = [item.item_id for item in self.provider.retrieve(self._query()).items]
        second = [item.item_id for item in self.provider.retrieve(self._query()).items]
        self.assertEqual(first, second)
        self.assertEqual(first, ["e-mid", "e-past"])

    def test_metadata_is_carried(self):
        result = self.provider.retrieve(self._query())
        item = next(item for item in result.items if item.item_id == "e-past")
        self.assertEqual(item.metadata["authority"], "user_explicit")
        self.assertEqual(item.metadata["available_at"], "2026-01-01T00:00:00Z")
        self.assertEqual(item.metadata["kind"], "fact")


if __name__ == "__main__":
    unittest.main()
