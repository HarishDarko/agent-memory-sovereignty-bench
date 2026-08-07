import tempfile
import unittest
from pathlib import Path

from benchmark.events import Event, Query


def _event(event_id: str) -> Event:
    return Event(
        event_id,
        "2026-06-01T00:00:00Z",
        "user_001",
        "personal",
        "user_explicit",
        "user",
        f"Marker text for {event_id}",
        subject="person_01",
    )


class ExampleAdapterContractTest(unittest.TestCase):
    def test_ingest_retrieve_delete_capability(self):
        from providers.example.adapter import make_example
        from benchmark.providers import CapabilityNotSupported

        with tempfile.TemporaryDirectory() as tmp:
            provider = make_example(Path(tmp))
            provider.reset()
            provider.ingest([_event("e1")])
            provider.await_ready()
            result = provider.retrieve(Query("q", "marker text", "user_001", "personal", "2026-07-01T00:00:00Z"))
            self.assertTrue(any(item.item_id == "e1" for item in result.items))
            with self.assertRaises(CapabilityNotSupported):
                provider.delete("e1")
            provider.cleanup()


if __name__ == "__main__":
    unittest.main()
