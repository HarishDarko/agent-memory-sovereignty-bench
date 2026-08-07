"""Hindsight adapter.

Hindsight (pinned commit 797faf7981ce9332e2ce7c922471b72b506b4065, v0.8.6,
MIT) is an API-server memory system with hybrid retrieval (BM25 + semantic +
graph + temporal decay) over Postgres/pgvector. This adapter is an HTTP
client: it creates one bank per provider data dir, stores memories with event
metadata, recalls via the hybrid endpoint, and performs as-of/principal/scope
filtering itself.

Controlled configuration: no LLM features (reflection/consolidation stay off)
until the Task 13 cost gate approves gateway-routed model calls; local
embeddings/rerankers are the offline path at the Phase 1 environment gate.
Request/response shapes below were confirmed against the pinned source AND
the running API on 2026-08-06 (contract tests are gated on
SOVBENCH_RUN_HINDSIGHT=1 and a reachable API):

- retain: POST /v1/default/banks/{bank_id}/memories with
  ``{"items": [MemoryItem], "async": false}``; MemoryItem carries content,
  ISO timestamp, string metadata, and document_id.
- recall: POST /v1/default/banks/{bank_id}/memories/recall with
  ``{"query", "budget", "max_tokens", "query_timestamp"}``; results carry
  ``id``/``text``/``metadata``/``scores.final``.
- banks: GET /v1/default/banks returns ``{"banks": [{bank_id, ...}]}``.
- per-event deletion: DELETE /v1/default/banks/{bank_id}/documents/{document_id}
  cascade-deletes a document and all its memory units (there is no
  per-memory-unit DELETE); each event is stored as its own document.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
import urllib.error
import urllib.request
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

HINDSIGHT_COMMIT = "797faf7981ce9332e2ce7c922471b72b506b4065"
DEFAULT_API_URL = os.environ.get("HINDSIGHT_API_URL", "http://127.0.0.1:8000")


class HindsightProvider(MemoryProvider):
    name = "hindsight"
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

    def __init__(self, data_dir: Path | None = None, api_url: str | None = None, timeout_s: float = 120.0):
        self.data_dir = Path(data_dir) if data_dir else Path(tempfile.mkdtemp(prefix="hindsight-"))
        self.api_url = (api_url or DEFAULT_API_URL).rstrip("/")
        self.bank_id = f"sovbench-{hashlib.sha256(str(self.data_dir).encode('utf-8')).hexdigest()[:12]}"
        self.timeout_s = timeout_s
        self._events: list[Event] = []
        self._seen: set[str] = set()
        self._ensure_bank()

    # -- HTTP plumbing -------------------------------------------------

    def _request(self, method: str, path: str, payload: dict | None = None) -> dict:
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(
            self.api_url + path,
            data=data,
            headers={"Content-Type": "application/json"},
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:500]
            raise RuntimeError(f"hindsight {method} {path} failed: HTTP {exc.code}: {body}") from exc

    def _ensure_bank(self) -> None:
        try:
            self._request("GET", "/health")
        except (RuntimeError, urllib.error.URLError) as exc:
            raise RuntimeError(
                f"Hindsight API not reachable at {self.api_url}; the server must run "
                f"per docker/providers/hindsight/ (contract tests are gated on "
                f"SOVBENCH_RUN_HINDSIGHT=1). {exc}"
            ) from exc
        banks = self._request("GET", "/v1/default/banks").get("banks", [])
        existing = [bank for bank in banks if bank.get("bank_id") == self.bank_id]
        if not existing:
            self._request("PUT", f"/v1/default/banks/{self.bank_id}", {"name": self.bank_id})

    # -- MemoryProvider contract --------------------------------------

    def reset(self) -> None:
        try:
            self._request("DELETE", f"/v1/default/banks/{self.bank_id}")
        except RuntimeError:
            pass
        self._ensure_bank()
        self._events = []
        self._seen = set()

    def ingest(self, events: list[Event]) -> IngestResult:
        fresh = [event for event in events if event.event_id not in self._seen]
        if not fresh:
            return IngestResult(ingested=0, latency_ms=0.0)
        items = []
        for event in fresh:
            metadata = {
                key: value
                for key, value in {
                    "event_id": event.event_id,
                    "principal": event.principal,
                    "scope": event.scope,
                    "available_at": event.available_at,
                    "authority": event.authority,
                    "source": event.source,
                    "subject": event.subject,
                    "kind": event.kind,
                }.items()
                if value is not None
            }
            items.append(
                {
                    "content": event.text,
                    "timestamp": event.available_at,
                    "document_id": event.event_id,
                    "metadata": metadata,
                }
            )
        started = time.perf_counter()
        response = self._request(
            "POST",
            f"/v1/default/banks/{self.bank_id}/memories",
            {"items": items, "async": False},
        )
        if response.get("success") is False:
            raise RuntimeError(f"hindsight retain reported failure: {response}")
        ingested = int(response.get("items_count", len(fresh)))
        self._events.extend(fresh)
        self._seen.update(event.event_id for event in fresh)
        return IngestResult(ingested=ingested, latency_ms=round((time.perf_counter() - started) * 1000.0, 3))

    def await_ready(self, timeout_s: float = 60.0) -> AwaitResult:
        started = time.perf_counter()
        self._request("GET", "/health")
        return AwaitResult(ready=True, time_to_ready_ms=(time.perf_counter() - started) * 1000.0, method="http")

    def delete(self, target: str) -> bool:
        event = next((item for item in self._events if item.event_id == target), None)
        if event is None:
            return False
        # Each event is stored as its own document; deleting the document
        # cascade-deletes all of its memory units (verified against the API).
        response = self._request(
            "DELETE", f"/v1/default/banks/{self.bank_id}/documents/{target}"
        )
        if response.get("success") is False:
            raise RuntimeError(f"hindsight document delete reported failure: {response}")
        self._events = [item for item in self._events if item.event_id != target]
        self._seen.discard(target)
        return True

    def retrieve(self, query: Query) -> RetrievalResult:
        started = time.perf_counter()
        result = self._request(
            "POST",
            f"/v1/default/banks/{self.bank_id}/memories/recall",
            {
                "query": query.question,
                "budget": "high",
                "max_tokens": 4096,
                "query_timestamp": query.as_of,
            },
        )
        by_id = {event.event_id: event for event in self._events}
        items: list[RetrievedItem] = []
        seen: set[str] = set()
        for item in _iter_recall_results(result):
            event_id = (item.get("metadata") or {}).get("event_id") or item.get("event_id")
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
            scores = item.get("scores") or {}
            score = scores.get("final") if isinstance(scores, dict) else None
            items.append(
                RetrievedItem(
                    item_id=event.event_id,
                    text=event.text,
                    score=float(score) if score is not None else None,
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
            raw={"matched": len(items)},
        )

    def snapshot(self) -> ProviderSnapshot:
        logical = hashing.sha256_text(
            "\n".join(sorted(event.event_id for event in self._events)) or "empty"
        )
        files = {"manifest": logical}
        return ProviderSnapshot(provider=self.name, state_hash=logical, files=files, events=tuple(self._events))

    def restore(self, snapshot: ProviderSnapshot) -> None:
        self.reset()
        if snapshot.events:
            self.ingest(list(snapshot.events))

    def export(self) -> dict:
        return {
            "format": "sovbench/hindsight-export/1",
            "hindsight_commit": HINDSIGHT_COMMIT,
            "events": [event.to_dict() for event in sorted(self._events, key=lambda event: event.event_id)],
        }

    def import_data(self, data) -> None:
        self.reset()
        events = [Event.from_dict(record) for record in data["events"]]
        self.ingest(events)

    def restart(self) -> None:
        pass  # state lives in the API's bank

    def stats(self) -> dict:
        return {"bank": self.bank_id, "memories": len(self._events), "hindsight_commit": HINDSIGHT_COMMIT}

    def cleanup(self) -> None:
        pass


def _iter_recall_results(result: dict) -> list[dict]:
    for key in ("results", "memories", "items", "data"):
        if isinstance(result.get(key), list):
            return [item for item in result[key] if isinstance(item, dict)]
    return [result] if result else []


def make_hindsight(
    data_dir: Path | None = None,
    api_url: str | None = None,
    timeout_s: float | None = None,
) -> HindsightProvider:
    kwargs = {}
    if timeout_s is not None:
        kwargs["timeout_s"] = timeout_s
    return HindsightProvider(data_dir=data_dir, api_url=api_url, **kwargs)
