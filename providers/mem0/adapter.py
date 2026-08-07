"""Mem0 OSS adapter.

Mem0 (pinned commit 3f39fba28f7781aaf581f64a4af39d017af65835, v2.0.17,
Apache-2.0) is a fact-extraction memory. The controlled configuration runs
fully offline: ``add(..., infer=False)`` avoids LLM extraction, chroma is the
local on-disk vector store, fastembed provides local CPU embeddings, and
telemetry is explicitly disabled (MEM0_TELEMETRY=false - the upstream default
is True via posthog).

The adapter preserves raw event IDs in metadata, keeps an event-id ->
memory-id mapping (mem0 has no delete-by-metadata API), and performs
as-of/principal/scope filtering after search. All adapter behavior is
recorded separately from upstream capabilities in manifests.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
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

MEM0_COMMIT = "3f39fba28f7781aaf581f64a4af39d017af65835"

# mem0's telemetry module reads MEM0_TELEMETRY at IMPORT time (default True
# via posthog). Force it before any mem0 import can happen.
os.environ.setdefault("MEM0_TELEMETRY", "false")


class Mem0Provider(MemoryProvider):
    name = "mem0"
    version = "0.1.0"
    capabilities = Capabilities(
        supports_snapshot=True,
        supports_restore=True,
        supports_delete=True,
        supports_export=True,
        supports_import=True,
        supports_restart=True,
        read_only_retrieval=True,
    )

    def __init__(
        self,
        data_dir: Path | None = None,
        timeout_s: float = 300.0,
        native_llm: dict | None = None,
    ):
        # native_llm enables mem0's product-native fact extraction
        # (infer=True) with an OpenAI-compatible LLM routed through the
        # benchmark gateway: {"base_url", "api_key", "model"}. Embeddings
        # stay local (fastembed) because no embedding API credentials exist;
        # that deviation is recorded in the native protocol document.
        self.data_dir = Path(data_dir) if data_dir else Path(tempfile.mkdtemp(prefix="mem0-"))
        self.mem0_dir = self.data_dir / "mem0"
        self.chroma_dir = self.data_dir / "chroma"
        self.registry_path = self.data_dir / "event_memory_ids.json"
        self.timeout_s = timeout_s
        self._events: list[Event] = []
        self._seen: set[str] = set()
        self._event_to_memory: dict[str, str] = {}
        self.native_llm = dict(native_llm) if native_llm else None
        self._memory = None
        self.reset()

    # -- mem0 plumbing --------------------------------------------------

    def _env(self) -> dict:
        env = dict(os.environ)
        env["MEM0_DIR"] = str(self.mem0_dir)
        env["MEM0_TELEMETRY"] = "false"  # upstream default is True (posthog)
        return env

    def _config(self) -> dict:
        config = {
            "vector_store": {
                "provider": "chroma",
                "config": {
                    "collection_name": "sovbench",
                    "path": str(self.chroma_dir),
                },
            },
            "embedder": {"provider": "fastembed", "config": {"model": "BAAI/bge-small-en-v1.5"}},
            "history_db_path": str(self.mem0_dir / "history.db"),
        }
        if self.native_llm:
            config["llm"] = {
                "provider": "openai",
                "config": {
                    "model": self.native_llm["model"],
                    "api_key": self.native_llm["api_key"],
                    "openai_base_url": self.native_llm["base_url"],
                    "temperature": 0.0,
                },
            }
        else:
            config["llm"] = {
                "provider": "openai",
                "config": {"model": "gpt-4o-mini", "api_key": "sovbench-no-llm-infer-false"},
            }
        return config

    def _memory_instance(self):
        if self._memory is None:
            try:
                from mem0 import Memory
            except ImportError as exc:
                raise RuntimeError(
                    "mem0ai is not installed in the benchmark environment; "
                    "install the pinned commit per providers/mem0/README.md"
                ) from exc
            with _env_override(self._env()):
                self._memory = Memory.from_config(self._config())
        return self._memory

    def _load_registry(self) -> None:
        if self.registry_path.exists():
            self._event_to_memory = json.loads(self.registry_path.read_text(encoding="utf-8"))

    def _save_registry(self) -> None:
        self.registry_path.write_text(
            json.dumps(self._event_to_memory, sort_keys=True, indent=2) + "\n", encoding="utf-8"
        )

    # -- MemoryProvider contract --------------------------------------

    def reset(self) -> None:
        if self._memory is not None:
            try:
                with _env_override(self._env()):
                    self._memory.reset()  # clears all memories via the API
            except Exception:  # noqa: BLE001 - a broken instance must not block reset
                pass
            self._memory = None
        _release_chroma()
        self.mem0_dir.mkdir(parents=True, exist_ok=True)
        self.chroma_dir.mkdir(parents=True, exist_ok=True)
        self._events = []
        self._seen = set()
        self._event_to_memory = {}
        self._save_registry()

    def ingest(self, events: list[Event]) -> IngestResult:
        fresh = [event for event in events if event.event_id not in self._seen]
        if not fresh:
            return IngestResult(ingested=0, latency_ms=0.0)
        memory = self._memory_instance()
        ingested = 0
        infer = self.native_llm is not None
        details: dict = (
            {"method": f"infer=True (native LLM {self.native_llm['model']} via gateway)"}
            if infer
            else {"method": "infer=False (no LLM)"}
        )
        for event in fresh:
            metadata = {
                "event_id": event.event_id,
                "principal": event.principal,
                "scope": event.scope,
                "available_at": event.available_at,
                "authority": event.authority,
                "source": event.source,
                "subject": event.subject,
                "kind": event.kind,
            }
            metadata = {key: value for key, value in metadata.items() if value is not None}
            result = None
            for attempt in (1, 2):
                try:
                    with _env_override(self._env()):
                        result = memory.add(
                            messages=[{"role": "user", "content": event.text}],
                            user_id=event.principal,
                            metadata=metadata,
                            infer=infer,
                        )
                    break
                except Exception as exc:  # noqa: BLE001
                    if attempt == 2:
                        # Transient store failures (e.g. chroma dedup/update
                        # races under native extraction) are recorded and the
                        # event's facts are simply absent - a measured outcome.
                        details.setdefault("storage_failures", []).append(
                            f"{event.event_id}: {type(exc).__name__}: {str(exc)[:120]}"
                        )
                        result = None
                        break
                    time.sleep(2.0)
            if result is None:
                continue
            memory_ids = [
                item["id"]
                for item in result.get("results", [])
                if isinstance(item, dict) and item.get("id")
            ]
            if infer:
                # Native extraction: the LLM decides what is worth storing, so
                # 0..N memories per event are all legitimate; deletion still
                # works per extracted memory id (registered below).
                for memory_id in memory_ids:
                    self._event_to_memory[f"{event.event_id}#{memory_id}"] = memory_id
                ingested += 1
            else:
                if len(memory_ids) != 1:
                    raise RuntimeError(f"mem0 add returned {len(memory_ids)} memories for {event.event_id}")
                self._event_to_memory[event.event_id] = memory_ids[0]
                ingested += 1
        self._events.extend(fresh)
        self._seen.update(event.event_id for event in fresh)
        self._save_registry()
        return IngestResult(ingested=ingested, latency_ms=0.0, details=details)

    def await_ready(self, timeout_s: float = 60.0) -> AwaitResult:
        started = time.perf_counter()
        self._memory_instance()  # construction is the readiness gate
        return AwaitResult(ready=True, time_to_ready_ms=(time.perf_counter() - started) * 1000.0, method="sync")

    def delete(self, target: str) -> bool:
        keys = [key for key in self._event_to_memory if key == target or key.startswith(f"{target}#")]
        if not keys:
            return False
        memory = self._memory_instance()
        for key in keys:
            with _env_override(self._env()):
                try:
                    memory.delete(memory_id=self._event_to_memory[key])
                except Exception as exc:  # noqa: BLE001
                    message = str(exc)
                    if "find" not in message.lower() and "not found" not in message.lower():
                        raise
                    # The memory no longer exists in the store (native
                    # extraction + dedup/consolidation may supersede it);
                    # deletion is therefore already effective.
            del self._event_to_memory[key]
        self._save_registry()
        self._events = [event for event in self._events if event.event_id != target]
        self._seen.discard(target)
        return True

    def retrieve(self, query: Query) -> RetrievalResult:
        started = time.perf_counter()
        memory = self._memory_instance()
        with _env_override(self._env()):
            result = memory.search(
                query=query.question,
                filters={"user_id": query.principal},
                limit=20,
            )
        by_id = {event.event_id: event for event in self._events}
        items: list[RetrievedItem] = []
        seen: set[str] = set()
        for item in result.get("results", []):
            metadata = item.get("metadata") or {}
            event_id = metadata.get("event_id")
            if not event_id or event_id in seen:
                continue
            event = by_id.get(event_id)
            if event is None:
                continue
            if event.available_at > query.as_of or event.principal != query.principal:
                continue
            if query.scope and event.scope != query.scope:
                continue
            seen.add(event_id)
            items.append(
                RetrievedItem(
                    item_id=event.event_id,
                    text=event.text,
                    score=float(item["score"]) if item.get("score") is not None else None,
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
            )
        return RetrievalResult(
            items=items,
            latency_ms=round((time.perf_counter() - started) * 1000.0, 3),
            raw={"matched": len(items), "total_results": len(result.get("results", []))},
        )

    def snapshot(self) -> ProviderSnapshot:
        files = {}
        for name, path in (
            ("event_memory_ids", self.registry_path),
            ("history.db", self.mem0_dir / "history.db"),
        ):
            if path.exists():
                files[name] = hashing.sha256_file(path)
        files["chroma"] = hashing.sha256_text(
            _dir_tree_hash(self.chroma_dir) or "empty"
        )
        logical = hashing.sha256_text(
            "\n".join(sorted(event.event_id for event in self._events)) or "empty"
        )
        state_hash = logical  # order-independent logical identity
        files["manifest"] = logical
        return ProviderSnapshot(provider=self.name, state_hash=state_hash, files=files, events=tuple(self._events))

    def restore(self, snapshot: ProviderSnapshot) -> None:
        self.reset()
        if snapshot.events:
            self.ingest(list(snapshot.events))

    def export(self) -> dict:
        return {
            "format": "sovbench/mem0-export/1",
            "mem0_commit": MEM0_COMMIT,
            "events": [event.to_dict() for event in sorted(self._events, key=lambda event: event.event_id)],
            "event_memory_ids": dict(sorted(self._event_to_memory.items())),
        }

    def import_data(self, data) -> None:
        self.reset()
        events = [Event.from_dict(record) for record in data["events"]]
        self.ingest(events)
        if data.get("event_memory_ids"):
            # Registry is rebuilt by ingest; keep upstream mapping as record only.
            self._event_to_memory = dict(data["event_memory_ids"])
            self._save_registry()

    def restart(self) -> None:
        self._memory = None  # force re-connect; state is on disk
        self._memory_instance()

    def stats(self) -> dict:
        return {
            "memories": len(self._events),
            "mem0_commit": MEM0_COMMIT,
            "vector_store": "chroma",
            "embedder": "fastembed",
            "llm": self.native_llm["model"] if self.native_llm else "none (infer=False)",
            "telemetry": "disabled",
        }

    def cleanup(self) -> None:
        self._memory = None
        _release_chroma()


def _dir_tree_hash(directory: Path) -> str:
    parts = []
    if directory.exists():
        for path in sorted(directory.rglob("*")):
            if path.is_file():
                parts.append(f"{path.relative_to(directory)}:{hashing.sha256_file(path)}")
    return hashing.sha256_text("\n".join(parts))


def _release_chroma() -> None:
    """Release chroma's file handles (required on Windows before deletion)."""
    try:
        from chromadb.api.client import SharedSystemClient

        SharedSystemClient.clear_system_cache()
    except Exception:  # noqa: BLE001 - best-effort resource release
        pass


class _env_override:
    """Temporarily apply provider env vars around mem0 calls."""

    def __init__(self, env: dict):
        self.env = env
        self.saved: dict[str, str | None] = {}

    def __enter__(self):
        for key, value in self.env.items():
            self.saved[key] = os.environ.get(key)
            os.environ[key] = value
        return self

    def __exit__(self, *exc):
        for key, value in self.saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        return False


def make_mem0(data_dir: Path | None = None, native_llm: dict | None = None) -> Mem0Provider:
    return Mem0Provider(data_dir=data_dir, native_llm=native_llm)
