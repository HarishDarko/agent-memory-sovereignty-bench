"""Deterministic benchmark clock - never wall-clock 'today' for scoring."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Iterable

from benchmark.events import Event


def parse_utc(iso: str) -> datetime:
    s = iso if iso.endswith("Z") else iso + "Z"
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)


def format_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize_iso(iso: str) -> str:
    return format_utc(parse_utc(iso))


@dataclass
class BenchmarkClock:
    """A clock that only advances when explicitly told to."""

    start_iso: str
    _current: datetime = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._current = parse_utc(self.start_iso)

    def now(self) -> str:
        return format_utc(self._current)

    def advance(self, **delta) -> None:
        self._current = self._current + timedelta(**delta)

    def set(self, iso: str) -> None:
        self._current = parse_utc(iso)


def events_available_by(events: Iterable[Event], as_of: str) -> list[Event]:
    """Future-leak rule: only events available by `as_of` are eligible."""
    cutoff = parse_utc(as_of)
    return [e for e in events if parse_utc(e.available_at) <= cutoff]
