"""OptMem adapter.

OptMem (pinned commit 1fb164cf39028047781f72ac3bb1e5a691c1dcb0) is a
single-file, dependency-free Python CLI maintaining an append-only memory log.
By design it has: no memory deletion (forget only drops rebuildable tree
summaries), no temporal filtering, no tenant model, and no ranking. This
adapter maps the benchmark's event/query contract onto OptMem and performs
as-of, principal, and scope filtering itself. Those are adapter behaviors and
are recorded separately from OptMem's own capabilities in the manifest.

The upstream project has no license file (all rights reserved by default), so
the pinned script is installed outside this repository (see
docs/research/provider-version-log.md) and is never vendored or redistributed.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from benchmark import hashing
from benchmark.events import Event, Query
from benchmark.providers import (
    AwaitResult,
    Capabilities,
    CapabilityNotSupported,
    IngestResult,
    MemoryProvider,
    ProviderSnapshot,
    RetrievedItem,
    RetrievalResult,
)
from providers.bm25 import tokenize

OPTMEM_COMMIT = "1fb164cf39028047781f72ac3bb1e5a691c1dcb0"
RECORD_RE = re.compile(r"#\d+ (\d{4}-\d{2}-\d{2}) \[([^\]]+)\] (.*)$")
DEFAULT_MEMO = Path(__file__).resolve().parent.parent.parent / ".optmem" / "memo"


class OptMemProvider(MemoryProvider):
    name = "optmem"
    version = "0.1.0"
    capabilities = Capabilities(
        supports_snapshot=True,
        supports_restore=True,
        supports_export=True,
        supports_import=True,
        supports_restart=True,
        read_only_retrieval=True,
        supports_delete=False,  # OptMem is append-only by design
    )

    def __init__(
        self,
        data_dir: Path | None = None,
        memo_path: Path | str | None = None,
        filtering: bool = True,
    ):
        # filtering=False is the product-native mode: OptMem's raw recall
        # behavior without adapter-side as-of/principal/scope filtering
        # (recorded as an adapter behavior difference, not an upstream one).
        self.data_dir = Path(data_dir) if data_dir else Path(tempfile.mkdtemp(prefix="optmem-"))
        self.filtering = filtering
        self.memory_dir = self.data_dir / "memory"
        self.memo_path = (
            Path(memo_path)
            if memo_path
            else Path(os.environ.get("OPTMEM_MEMO_PATH") or DEFAULT_MEMO)
        )
        if not self.memo_path.exists():
            raise FileNotFoundError(
                f"OptMem script not found at {self.memo_path}; install the pinned copy "
                "per providers/optmem/README.md"
            )
        self._events: list[Event] = []
        self._seen: set[str] = set()
        self.reset()

    # -- OptMem CLI plumbing -------------------------------------------

    def _run(self, *args: str, timeout: float = 60.0) -> str:
        env = dict(os.environ)
        env["MEMORY_DIR"] = str(self.memory_dir)
        proc = subprocess.run(
            [sys.executable, str(self.memo_path), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
            env=env,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"memo {' '.join(args)} failed: {(proc.stderr or proc.stdout).strip()[:400]}"
            )
        return proc.stdout

    # -- MemoryProvider contract --------------------------------------

    def reset(self) -> None:
        if self.memory_dir.exists():
            shutil.rmtree(self.memory_dir)
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self._run("init")
        self._events = []
        self._seen = set()

    def ingest(self, events: list[Event]) -> IngestResult:
        fresh = [event for event in events if event.event_id not in self._seen]
        if not fresh:
            return IngestResult(ingested=0, latency_ms=0.0)
        fresh.sort(key=lambda event: (event.available_at, event.event_id))
        lines = [f"{event.available_at[:10]} [{event.event_id}] {event.text}" for event in fresh]
        for line in lines:
            if len(line.encode("utf-8")) > 280:
                raise RuntimeError(
                    f"OptMem ENTRY_CHARS=280 exceeded by {len(line.encode('utf-8'))} bytes; "
                    "shrink the event text or raise OptMem's ENTRY_CHARS"
                )
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".txt", delete=False) as handle:
            handle.write("\n".join(lines) + "\n")
            import_path = handle.name
        try:
            self._run("import", import_path)
        finally:
            os.unlink(import_path)
        self._events.extend(fresh)
        self._seen.update(event.event_id for event in fresh)
        return IngestResult(ingested=len(fresh), latency_ms=0.0)

    def await_ready(self, timeout_s: float = 60.0) -> AwaitResult:
        return AwaitResult(ready=True, time_to_ready_ms=0.0, method="sync")

    def delete(self, target: str):
        raise CapabilityNotSupported(
            "OptMem is append-only by design; the upstream tool never edits or deletes "
            "log records (forget only drops rebuildable summaries)"
        )

    def retrieve(self, query: Query) -> RetrievalResult:
        started = time.perf_counter()
        terms = tokenize(query.question)[:8]
        if not terms:
            return RetrievalResult(items=[], latency_ms=0.0, raw={"terms": []})
        pattern = "|".join(re.escape(term) for term in terms)
        try:
            output = self._run("recall", pattern)
        except RuntimeError:
            return RetrievalResult(items=[], latency_ms=0.0, raw={"terms": terms, "recall_error": True})
        by_id = {event.event_id: event for event in self._events}
        items: list[RetrievedItem] = []
        for line in output.splitlines():
            match = RECORD_RE.match(line)
            if not match:
                continue
            event = by_id.get(match.group(2))
            if event is None:
                continue
            if self.filtering:
                if event.available_at > query.as_of or event.principal != query.principal:
                    continue
                if query.scope and event.scope != query.scope:
                    continue
            items.append(
                RetrievedItem(
                    item_id=event.event_id,
                    text=event.text,
                    score=None,
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
            raw={"terms": terms, "recall_matches": len(items)},
        )

    def snapshot(self) -> ProviderSnapshot:
        files = {}
        log_path = self.memory_dir / "LOG.txt"
        if log_path.exists():
            files["LOG.txt"] = hashing.sha256_file(log_path)
        logical = hashing.sha256_text(
            "\n".join(sorted(event.event_id for event in self._events)) or "empty"
        )
        return ProviderSnapshot(
            provider=self.name,
            state_hash=hashing.sha256_text(logical + "|" + files.get("LOG.txt", "missing")),
            files=files,
            events=tuple(self._events),
        )

    def restore(self, snapshot: ProviderSnapshot) -> None:
        self.reset()
        if snapshot.events:
            self.ingest(list(snapshot.events))

    def export(self) -> dict:
        return {
            "format": "sovbench/optmem-export/1",
            "memo_commit": OPTMEM_COMMIT,
            "events": [event.to_dict() for event in sorted(self._events, key=lambda event: event.event_id)],
        }

    def import_data(self, data) -> None:
        self.reset()
        events = [Event.from_dict(record) for record in data["events"]]
        self.ingest(events)

    def restart(self) -> None:
        # OptMem state lives on disk; a "restart" is a no-op by construction.
        pass

    def stats(self) -> dict:
        return {
            "log_records": len(self._events),
            "memo_commit": OPTMEM_COMMIT,
            "memo_path": str(self.memo_path),
        }

    def cleanup(self) -> None:
        pass


def make_optmem(
    data_dir: Path | None = None,
    memo_path: Path | str | None = None,
    filtering: bool = True,
) -> OptMemProvider:
    return OptMemProvider(data_dir=data_dir, memo_path=memo_path, filtering=filtering)


if __name__ == "__main__":
    # Container placeholder until the provider-run orchestrator is wired:
    # verify the pinned tool works, then stay alive.
    provider = OptMemProvider(Path("/provider-state"), memo_path=os.environ.get("OPTMEM_MEMO_PATH", "/opt/optmem/memo"))
    print(f"optmem adapter ready: commit={OPTMEM_COMMIT} records={provider.stats()['log_records']}", flush=True)
    import time as _time

    while True:
        _time.sleep(3600)
