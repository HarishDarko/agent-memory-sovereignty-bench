import unittest

from benchmark.clock import BenchmarkClock, events_available_by
from benchmark.events import Event


class TestBenchmarkClock(unittest.TestCase):
    def test_fixed_now(self):
        clock = BenchmarkClock("2026-08-01T00:00:00Z")
        self.assertEqual(clock.now(), "2026-08-01T00:00:00Z")
        self.assertEqual(clock.now(), "2026-08-01T00:00:00Z")  # never advances on its own

    def test_advance_and_set(self):
        clock = BenchmarkClock("2026-08-01T00:00:00Z")
        clock.advance(days=1)
        self.assertEqual(clock.now(), "2026-08-02T00:00:00Z")
        clock.set("2026-03-15T09:30:00Z")
        self.assertEqual(clock.now(), "2026-03-15T09:30:00Z")

    def test_deterministic_across_instances(self):
        a = BenchmarkClock("2026-08-01T00:00:00Z")
        b = BenchmarkClock("2026-08-01T00:00:00Z")
        self.assertEqual(a.now(), b.now())

    def test_events_available_by(self):
        events = [
            Event("e1", "2026-01-01T00:00:00Z", "p", "personal", "user_explicit", "s", "old"),
            Event("e2", "2026-08-01T00:00:00Z", "p", "personal", "user_explicit", "s", "boundary"),
            Event("e3", "2026-09-01T00:00:00Z", "p", "personal", "user_explicit", "s", "future"),
        ]
        available = events_available_by(events, "2026-08-01T00:00:00Z")
        ids = {e.event_id for e in available}
        self.assertEqual(ids, {"e1", "e2"})  # boundary inclusive, future excluded


if __name__ == "__main__":
    unittest.main()
