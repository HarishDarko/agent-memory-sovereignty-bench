import unittest

from benchmark.capability_provider_views import native_retrieve
from benchmark.events import Event, Query


def _event(event_id, *, principal="user_001", scope="personal", available_at="2026-06-01T00:00:00Z"):
    return Event(
        event_id,
        available_at,
        principal,
        scope,
        "user_explicit",
        "user",
        f"Marker {event_id}",
        subject="person_01",
    )


class _GBrainFake:
    name = "gbrain"

    def __init__(self):
        self._events = [
            _event("eligible"),
            _event("future", available_at="2026-08-01T00:00:00Z"),
            _event("other", principal="user_002"),
        ]

    def _run(self, *args):
        return "\n".join(f"[0.9] {event.event_id} -- {event.text}" for event in self._events)


class _MemoryFake:
    def search(self, **kwargs):
        return {
            "results": [
                {
                    "id": "native-1",
                    "memory": "Marker future",
                    "score": 0.8,
                    "metadata": {
                        "event_id": "future",
                        "principal": "user_001",
                        "scope": "personal",
                        "available_at": "2026-08-01T00:00:00Z",
                        "authority": "user_explicit",
                        "source": "user",
                        "subject": "person_01",
                        "kind": "fact",
                    },
                }
            ]
        }


class _Mem0Fake:
    name = "mem0"
    _events = [_event("future", available_at="2026-08-01T00:00:00Z")]

    def _memory_instance(self):
        return _MemoryFake()

    def _env(self):
        return {}


class _HindsightFake:
    name = "hindsight"
    bank_id = "bank"
    _events = [_event("other", principal="user_002")]

    def _request(self, method, path, payload):
        self.payload = payload
        return {
            "results": [
                {
                    "text": "Marker other",
                    "metadata": {
                        "event_id": "other",
                        "principal": "user_002",
                        "scope": "personal",
                        "available_at": "2026-06-01T00:00:00Z",
                        "authority": "user_explicit",
                        "source": "user",
                        "subject": "person_01",
                        "kind": "fact",
                    },
                    "scores": {"final": 0.7},
                }
            ]
        }


class NativeProviderViewTests(unittest.TestCase):
    def setUp(self):
        self.query = Query("q", "Which marker applies?", "user_001", "personal", "2026-07-01T00:00:00Z")

    def test_gbrain_view_returns_unfiltered_product_search_results(self):
        result = native_retrieve(_GBrainFake(), self.query)
        self.assertEqual([item.item_id for item in result.items], ["eligible", "future", "other"])
        self.assertEqual(result.raw["native_scope"], "global-cli-search")

    def test_mem0_view_retains_native_user_filter_but_not_as_of_post_filter(self):
        result = native_retrieve(_Mem0Fake(), self.query)
        self.assertEqual([item.item_id for item in result.items], ["future"])
        self.assertEqual(result.raw["native_scope"], "user_id-filter")

    def test_hindsight_view_retains_required_query_timestamp_but_not_principal_post_filter(self):
        provider = _HindsightFake()
        result = native_retrieve(provider, self.query)
        self.assertEqual([item.item_id for item in result.items], ["other"])
        self.assertEqual(provider.payload["query_timestamp"], self.query.as_of)
        self.assertEqual(result.raw["native_scope"], "bank+query_timestamp")

    def test_immutable_event_catalog_keeps_stale_deleted_results_observable(self):
        provider = _HindsightFake()
        deleted = provider._events[0]
        provider._events = []  # normal adapter bookkeeping after delete
        result = native_retrieve(provider, self.query, event_catalog=[deleted])
        self.assertEqual([item.item_id for item in result.items], ["other"])


if __name__ == "__main__":
    unittest.main()
