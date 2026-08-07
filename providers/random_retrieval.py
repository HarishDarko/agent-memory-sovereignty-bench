"""Random-retrieval negative control.

Retrieval selects a deterministic pseudo-random sample of eligible events. If
this control ever approaches useful retrieval scores, the scorer or pipeline
is producing artifacts. Controls are excluded from provider rankings.
"""

from __future__ import annotations

import hashlib
import random
from pathlib import Path

from benchmark import hashing
from benchmark.events import Event, Query
from benchmark.providers import (
    AwaitResult,
    Capabilities,
    IngestResult,
    MemoryProvider,
    ProviderSnapshot,
    RetrievedItem,
    RetrievalResult,
)


class RandomRetrievalProvider(MemoryProvider):
    name = "random-retrieval"
    version = "0.1.0"
    capabilities = Capabilities(
        supports_snapshot=True,
        supports_restore=True,
        supports_delete=True,
        read_only_retrieval=True,
    )

    def __init__(self, data_dir: Path | None = None, k: int = 10, seed: int = 20260805):
        self.data_dir = Path(data_dir) if data_dir else None
        self.k = k
        self.seed = seed
        self._events: list[Event] = []

    def reset(self) -> None:
        self._events = []

    def ingest(self, events: list[Event]) -> IngestResult:
        seen = {event.event_id for event in self._events}
        ingested = 0
        for event in events:
            if event.event_id not in seen:
                self._events.append(event)
                seen.add(event.event_id)
                ingested += 1
        return IngestResult(ingested=ingested, latency_ms=0.0)

    def await_ready(self, timeout_s: float = 60.0) -> AwaitResult:
        return AwaitResult(ready=True, time_to_ready_ms=0.0, method="sync")

    def delete(self, target: str) -> bool:
        before = len(self._events)
        self._events = [event for event in self._events if event.event_id != target]
        return len(self._events) != before

    def retrieve(self, query: Query) -> RetrievalResult:
        eligible = [
            event
            for event in self._events
            if event.available_at <= query.as_of
            and event.principal == query.principal
            and (not query.scope or event.scope == query.scope)
        ]
        digest = hashlib.sha256(f"{query.query_id}|{self.seed}".encode("utf-8")).hexdigest()
        rng = random.Random(int(digest[:8], 16))
        chosen = rng.sample(eligible, min(self.k, len(eligible))) if eligible else []
        chosen.sort(key=lambda event: event.event_id)
        items = [
            RetrievedItem(
                item_id=event.event_id,
                text=event.text,
                score=round(rng.random(), 6),
                metadata={
                    "principal": event.principal,
                    "subject": event.subject,
                    "scope": event.scope,
                    "authority": event.authority,
                    "source": event.source,
                    "available_at": event.available_at,
                    "kind": event.kind,
                },
            )
            for event in chosen
        ]
        return RetrievalResult(
            items=items,
            latency_ms=0.0,
            raw={"control": "random", "eligible": len(eligible), "sampled": len(items), "seed": self.seed},
        )

    def snapshot(self) -> ProviderSnapshot:
        state = hashing.sha256_text(
            "\n".join(sorted(event.event_id for event in self._events)) or "empty"
        )
        return ProviderSnapshot(provider=self.name, state_hash=state, files={}, events=tuple(self._events))

    def restore(self, snapshot: ProviderSnapshot) -> None:
        self.reset()
        if snapshot.events:
            self.ingest(list(snapshot.events))

    def stats(self) -> dict:
        return {"events": len(self._events), "k": self.k, "seed": self.seed}

    def cleanup(self) -> None:
        pass
