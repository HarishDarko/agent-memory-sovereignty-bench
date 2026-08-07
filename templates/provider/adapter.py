"""Example provider adapter template for AMSB.

Copy this directory to ``providers/<name>/``, rename the class and factory,
implement the required methods, then register the provider in
``providers/registry.json``:

.. code-block:: json

    "example": {
      "name": "example",
      "static": true,
      "containerized": false,
      "factory": "providers.example.adapter:make_example",
      "factory_kwargs_env": {},
      "tracks": {"controlled": true, "native": false},
      "contract_status": "declared",
      "manifest": "providers/example/manifest.toml",
      "meta": { ... exact pins and metadata ... }
    }

See ``docs/adding-a-provider.md`` for the full tutorial.
"""

from __future__ import annotations

from pathlib import Path

from benchmark.events import Event, Query
from benchmark.providers import (
    Capabilities,
    CapabilityNotSupported,
    IngestResult,
    MemoryProvider,
    ProviderSnapshot,
    RetrievalResult,
    RetrievedItem,
)


class ExampleProvider(MemoryProvider):
    """Level-1 controlled retrieval provider (example)."""

    name = "example"
    version = "0.1.0"
    capabilities = Capabilities(
        read_only_retrieval=True,
        supports_snapshot=True,
        supports_restore=True,
        supports_delete=False,
    )

    def __init__(self, data_dir: Path | None = None):
        self.data_dir = Path(data_dir) if data_dir else Path(".") / ".example-state"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._events: dict[str, Event] = {}

    def reset(self) -> None:
        self._events.clear()

    def ingest(self, events: list[Event]) -> IngestResult:
        for event in events:
            self._events[event.event_id] = event
        return IngestResult(ingested=len(events))

    def await_ready(self, timeout_s: float = 60.0):
        from benchmark.providers import AwaitResult

        return AwaitResult(ready=True, method="sync")

    def retrieve(self, query: Query) -> RetrievalResult:
        terms = {term.lower() for term in query.question.split() if len(term) > 2}
        items = [
            RetrievedItem(event.event_id, event.text, 1.0, {"principal": event.principal})
            for event in self._events.values()
            if terms.intersection(event.text.lower().split())
        ][:5]
        return RetrievalResult(items)

    def snapshot(self) -> ProviderSnapshot:
        return ProviderSnapshot(
            provider=self.name,
            state_hash=str(len(self._events)),
            events=tuple(self._events.values()),
        )

    def restore(self, snapshot: ProviderSnapshot) -> None:
        self._events = {event.event_id: event for event in snapshot.events}

    def stats(self) -> dict:
        return {"events": len(self._events)}

    def cleanup(self) -> None:
        pass

    def delete(self, target: str):
        raise CapabilityNotSupported(f"{self.name} does not support delete")


def make_example(data_dir: Path | None = None) -> ExampleProvider:
    return ExampleProvider(data_dir=data_dir)


def native_retrieve(provider: ExampleProvider, query: Query, event_catalog=None) -> RetrievalResult:
    """Optional Level-3 hook: provider-native retrieval view.

    Declare it in the registry entry as ``"native_view":
    "providers.example.adapter:native_retrieve"``. The central runner then
    calls this instead of the built-in views.
    """
    return provider.retrieve(query)
