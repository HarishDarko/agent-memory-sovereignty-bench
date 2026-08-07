"""MemoryProvider interface and capability model."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

from benchmark.events import Event, Query


@dataclass(frozen=True)
class Capabilities:
    supports_snapshot: bool = False
    supports_restore: bool = False
    supports_delete: bool = False
    supports_export: bool = False
    supports_import: bool = False
    read_only_retrieval: bool = False  # retrieval never mutates provider state
    uses_ground_truth: bool = False  # True only for the oracle control
    network_required: bool = False
    async_indexing: bool = False
    supports_restart: bool = False  # state survives a provider restart

    def to_dict(self) -> dict:
        return {
            "supports_snapshot": self.supports_snapshot,
            "supports_restore": self.supports_restore,
            "supports_delete": self.supports_delete,
            "supports_export": self.supports_export,
            "supports_import": self.supports_import,
            "read_only_retrieval": self.read_only_retrieval,
            "uses_ground_truth": self.uses_ground_truth,
            "network_required": self.network_required,
            "async_indexing": self.async_indexing,
            "supports_restart": self.supports_restart,
        }


class CapabilityNotSupported(RuntimeError):
    """Raised when a provider does not support an operation. Recorded, never faked."""


@dataclass
class RetrievedItem:
    item_id: str
    text: str
    score: Optional[float] = None
    metadata: dict = field(default_factory=dict)


@dataclass
class RetrievalResult:
    items: list[RetrievedItem]
    latency_ms: float = 0.0
    raw: dict = field(default_factory=dict)
    mutated: bool = False  # set by the query-mutation check


@dataclass
class IngestResult:
    ingested: int
    latency_ms: float = 0.0
    details: dict = field(default_factory=dict)


@dataclass
class AwaitResult:
    ready: bool
    time_to_ready_ms: float = 0.0
    method: str = "sync"
    details: dict = field(default_factory=dict)


@dataclass
class ProviderSnapshot:
    provider: str
    state_hash: str
    files: dict = field(default_factory=dict)
    events: tuple[Event, ...] = ()
    taken_at: str = ""


class MemoryProvider(ABC):
    """Provider adapter interface (see canonical plan section 27)."""

    name: str = "abstract"
    version: str = "0.0.0"
    capabilities: Capabilities = Capabilities()

    @abstractmethod
    def reset(self) -> None:
        """Return the provider to an empty, fresh state."""

    @abstractmethod
    def ingest(self, events: list[Event]) -> IngestResult:
        """Store events. Duplicate event_ids should be deduplicated."""

    @abstractmethod
    def await_ready(self, timeout_s: float = 60.0) -> AwaitResult:
        """Poll until newly written facts are searchable (freshness latency)."""

    @abstractmethod
    def retrieve(self, query: Query) -> RetrievalResult:
        """Retrieve evidence for the query under its principal/scope/as_of."""

    @abstractmethod
    def snapshot(self) -> ProviderSnapshot:
        """Hash the current provider state for mutation/isolation checks."""

    @abstractmethod
    def restore(self, snapshot: ProviderSnapshot) -> None:
        """Restore from a baseline snapshot (clone-per-query isolation)."""

    @abstractmethod
    def stats(self) -> dict:
        """Operational stats (counts, sizes) for the manifest."""

    @abstractmethod
    def cleanup(self) -> None:
        """Close resources. State may be retained for inspection."""

    def delete(self, target: str) -> Any:
        raise CapabilityNotSupported(f"{self.name} does not support delete")

    def export(self) -> Any:
        raise CapabilityNotSupported(f"{self.name} does not support export")

    def import_data(self, data: Any) -> None:
        raise CapabilityNotSupported(f"{self.name} does not support import")

    def restart(self) -> None:
        raise CapabilityNotSupported(f"{self.name} does not support restart")
