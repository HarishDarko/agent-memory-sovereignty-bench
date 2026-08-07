"""Oracle control: returns exact gold evidence. Uses ground truth BY DESIGN."""

from __future__ import annotations

from pathlib import Path

from benchmark import hashing
from benchmark.events import Event, GroundTruth, Query
from benchmark.providers import (
    AwaitResult,
    Capabilities,
    IngestResult,
    MemoryProvider,
    ProviderSnapshot,
    RetrievedItem,
    RetrievalResult,
)


class OracleProvider(MemoryProvider):
    name = "oracle"
    version = "0.1.0"
    capabilities = Capabilities(
        supports_snapshot=True,
        supports_restore=True,
        supports_delete=True,
        read_only_retrieval=True,
        uses_ground_truth=True,
    )

    def __init__(self, gold_events: dict[str, list[Event]], data_dir: Path | None = None):
        self.gold_events = gold_events
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
        events = [e for e in self.gold_events.get(query.query_id, []) if e.available_at <= query.as_of]
        items = [
            RetrievedItem(
                item_id=e.event_id,
                text=e.text,
                score=1.0,
                metadata={
                    "principal": e.principal,
                    "scope": e.scope,
                    "available_at": e.available_at,
                    "authority": e.authority,
                    "source": e.source,
                    "kind": e.kind,
                    "subject": e.subject,
                    "valid_from": e.valid_from,
                    "valid_to": e.valid_to,
                },
            )
            for e in events
        ]
        return RetrievalResult(items=items, latency_ms=0.0, raw={"control": "oracle"})

    def delete(self, target: str) -> bool:
        self._events = [event for event in self._events if event.event_id != target]
        return True

    def snapshot(self) -> ProviderSnapshot:
        return ProviderSnapshot(
            provider=self.name,
            state_hash=hashing.sha256_text("oracle-immutable"),
            files={},
            events=(),
        )

    def restore(self, snapshot: ProviderSnapshot) -> None:
        self.reset()

    def stats(self) -> dict:
        return {"gold_queries": len(self.gold_events)}

    def cleanup(self) -> None:
        pass


def build_oracle(events: list[Event], gold: dict[str, GroundTruth]) -> OracleProvider:
    by_id = {e.event_id: e for e in events}
    gold_events: dict[str, list[Event]] = {}
    for qid, row in gold.items():
        gold_events[qid] = [by_id[i] for i in row.gold_event_ids if i in by_id]
    return OracleProvider(gold_events=gold_events)


def make_oracle(events: list[Event], gold: dict[str, GroundTruth], data_dir: Path | None = None) -> OracleProvider:
    return build_oracle(events, gold)
