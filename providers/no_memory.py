"""No-memory control: retrieval always returns empty evidence."""

from __future__ import annotations

from pathlib import Path

from benchmark import hashing
from benchmark.events import Event, Query
from benchmark.providers import (
    AwaitResult,
    Capabilities,
    IngestResult,
    MemoryProvider,
    ProviderSnapshot,
    RetrievalResult,
)


class NoMemoryProvider(MemoryProvider):
    name = "no-memory"
    version = "0.1.0"
    capabilities = Capabilities(
        supports_snapshot=True,
        supports_restore=True,
        supports_delete=True,
        read_only_retrieval=True,
    )

    def __init__(self, data_dir: Path | None = None):
        self.data_dir = Path(data_dir) if data_dir else None
        self._events: list[Event] = []

    def reset(self) -> None:
        self._events = []

    def ingest(self, events: list[Event]) -> IngestResult:
        self._events = list(events)
        return IngestResult(ingested=len(events), latency_ms=0.0)

    def await_ready(self, timeout_s: float = 60.0) -> AwaitResult:
        return AwaitResult(ready=True, time_to_ready_ms=0.0, method="sync")

    def retrieve(self, query: Query) -> RetrievalResult:
        return RetrievalResult(items=[], latency_ms=0.0, raw={"control": "no-memory"})

    def delete(self, target: str) -> bool:
        self._events = [event for event in self._events if event.event_id != target]
        return True

    def snapshot(self) -> ProviderSnapshot:
        return ProviderSnapshot(
            provider=self.name,
            state_hash=hashing.sha256_text("no-memory"),
            files={},
            events=(),
        )

    def restore(self, snapshot: ProviderSnapshot) -> None:
        self.reset()

    def stats(self) -> dict:
        return {"ingested": len(self._events)}

    def cleanup(self) -> None:
        pass


def make_no_memory(data_dir: Path) -> NoMemoryProvider:
    return NoMemoryProvider(data_dir=data_dir)
