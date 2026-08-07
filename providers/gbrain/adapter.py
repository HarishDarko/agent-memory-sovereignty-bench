"""GBrain adapter.

GBrain (pinned commit 15b9863d13635d173562a54f55a1d388bfcf546b, v0.42.73.2,
MIT) keeps markdown + frontmatter as the system of record and a derived
PGLite index for search. This adapter writes one page per event, syncs and
indexes through the pinned `gbrain` CLI, and performs as-of/principal/scope
filtering itself. The controlled configuration disables LLM/network features
(expansion, reranker) and uses keyword/hybrid retrieval only.

The CLI is installed externally at a pinned commit (see
docs/research/provider-version-log.md); `GBRAIN_HOME` isolates each brain.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
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

GBRAIN_COMMIT = "15b9863d13635d173562a54f55a1d388bfcf546b"


def _frontmatter(event: Event) -> dict:
    return {
        "event_id": event.event_id,
        "principal": event.principal,
        "scope": event.scope,
        "available_at": event.available_at,
        "authority": event.authority,
        "source": event.source,
        "subject": event.subject,
        "kind": event.kind,
    }


def _render_page(event: Event) -> str:
    fields = "\n".join(f"{key}: {value}" for key, value in _frontmatter(event).items() if value is not None)
    return f"---\n{fields}\n---\n\n{event.text}\n"


class GBrainProvider(MemoryProvider):
    name = "gbrain"
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
        gbrain_bin: Path | str | None = None,
        bun_bin: Path | str | None = None,
        timeout_s: float = 300.0,
    ):
        self.data_dir = Path(data_dir) if data_dir else Path(tempfile.mkdtemp(prefix="gbrain-"))
        self.home = self.data_dir / "gbrain-home"
        self.brain_dir = self.home / "brain"
        self.gbrain_bin = Path(gbrain_bin) if gbrain_bin else Path(os.environ.get("GBRAIN_BIN", "gbrain"))
        self.bun_bin = bun_bin or os.environ.get("BUN_BIN", "bun")
        self.timeout_s = timeout_s
        self._trash: list[Path] = []
        self._events: list[Event] = []
        self._seen: set[str] = set()
        self._ensure_brain()

    # -- CLI plumbing --------------------------------------------------

    def _env(self) -> dict:
        env = dict(os.environ)
        env["GBRAIN_HOME"] = str(self.home)
        env.setdefault("CI", "1")  # non-interactive
        return env

    def _run(self, *args: str, timeout: float | None = None) -> str:
        command = [str(self.gbrain_bin), *args]
        if str(self.gbrain_bin).endswith((".ts", ".mts")):
            command = [str(self.bun_bin), str(self.gbrain_bin), *args]
        proc = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout or self.timeout_s,
            env=self._env(),
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"gbrain {' '.join(args)} failed: {(proc.stderr or proc.stdout).strip()[:500]}"
            )
        return proc.stdout

    def _run_allow_failure(self, *args: str, timeout: float | None = None) -> tuple[int, str]:
        command = [str(self.gbrain_bin), *args]
        if str(self.gbrain_bin).endswith((".ts", ".mts")):
            command = [str(self.bun_bin), str(self.gbrain_bin), *args]
        proc = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout or self.timeout_s,
            env=self._env(),
        )
        return proc.returncode, (proc.stderr or proc.stdout).strip()

    def _git(self, *args: str, timeout: float = 60.0) -> str:
        proc = subprocess.run(
            ["git", "-C", str(self.brain_dir), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
            env=dict(os.environ, GIT_AUTHOR_NAME="sovbench", GIT_AUTHOR_EMAIL="sovbench@local",
                     GIT_COMMITTER_NAME="sovbench", GIT_COMMITTER_EMAIL="sovbench@local"),
        )
        if proc.returncode != 0:
            raise RuntimeError(f"git {' '.join(args)} failed: {(proc.stderr or proc.stdout).strip()[:400]}")
        return proc.stdout

    def _git_commit(self, message: str) -> str:
        self._git("add", "-A")
        status = self._git("status", "--porcelain")
        if not status.strip():
            return "noop"
        return self._git("commit", "-m", message).strip()

    def _ensure_brain(self) -> None:
        if self.home.exists() and not (self.home / "gbrain.yml").exists() and (self.home / ".gbrain").exists():
            # Partial state from an interrupted run: recreate the home cleanly.
            trash = self.data_dir / f"trash-{int(time.time() * 1000)}"
            os.rename(self.home, trash)
            self._trash.append(trash)
        self.brain_dir.mkdir(parents=True, exist_ok=True)
        if not (self.brain_dir / ".git").exists():
            self._git("init", "-q")
            self._git("config", "user.name", "sovbench")
            self._git("config", "user.email", "sovbench@local")
            self._git_commit("initial brain")
        if not (self.home / "gbrain.yml").exists():
            self.home.mkdir(parents=True, exist_ok=True)
            # Controlled configuration: NO embedding provider (--no-embedding),
            # so retrieval is keyword-based and no external LLM/embedding key
            # is ever required or contacted. Recorded in config.toml.
            self._run("init", "--pglite", "--no-embedding")
            # init registers a default source without our path; replace it in
            # this isolated GBRAIN_HOME (remove is tolerated if absent).
            self._run_allow_failure("sources", "remove", "default", "--confirm-destructive")
            self._run("sources", "add", "bench", "--path", str(self.brain_dir), "--force")
            self._run("sources", "default", "bench")

    # -- MemoryProvider contract --------------------------------------

    def reset(self) -> None:
        if self.home.exists():
            trash = self.data_dir / f"trash-{int(time.time() * 1000)}"
            try:
                os.rename(self.home, trash)  # rename works even when a host
                self._trash.append(trash)    # watcher briefly holds a file
                for old in list(self._trash[:-1]):  # reclaim older trash
                    try:
                        _rmtree_retry(old, tries=2)
                    except OSError:
                        pass
                self._trash = self._trash[-1:]
            except OSError:
                _rmtree_retry(self.home)     # fallback: best-effort delete
        self._ensure_brain()
        self._events = []
        self._seen = set()

    def ingest(self, events: list[Event]) -> IngestResult:
        fresh = [event for event in events if event.event_id not in self._seen]
        if not fresh:
            return IngestResult(ingested=0, latency_ms=0.0)
        for event in fresh:
            page = self.brain_dir / f"{event.event_id}.md"
            page.write_text(_render_page(event), encoding="utf-8")
        self._git_commit(f"ingest {len(fresh)} events")
        self._run("sync", "--no-hard-deadline")
        self._events.extend(fresh)
        self._seen.update(event.event_id for event in fresh)
        return IngestResult(ingested=len(fresh), latency_ms=0.0, details={"system_of_record": "markdown+frontmatter"})

    def await_ready(self, timeout_s: float = 60.0) -> AwaitResult:
        started = time.perf_counter()
        self._run("status", timeout=timeout_s)
        return AwaitResult(ready=True, time_to_ready_ms=(time.perf_counter() - started) * 1000.0, method="cli")

    def delete(self, target: str) -> bool:
        page = self.brain_dir / f"{target}.md"
        existed = page.exists()
        if existed:
            page.unlink()
            self._git_commit(f"delete {target}")
            self._run("sync", "--no-hard-deadline")
        self._events = [event for event in self._events if event.event_id != target]
        self._seen.discard(target)
        return existed

    def retrieve(self, query: Query) -> RetrievalResult:
        started = time.perf_counter()
        terms = re.findall(r"[a-z0-9]{2,}", query.question.lower())
        terms = [term for term in terms if term not in _STOPWORDS][:6]
        if not terms:
            return RetrievalResult(items=[], latency_ms=0.0, raw={"terms": []})
        # GBrain's no-embedding keyword search returns a fixed small top-N.
        # Adapter mapping: run the full query first, then one search per
        # significant term, and union the results. Deterministic; the reader
        # token budget still bounds the evidence actually sent.
        searches = [" ".join(terms), *terms]
        matched: dict[str, float] = {}
        raw_searches: list[str] = []
        for query_text in searches:
            try:
                output = self._run("search", query_text)
            except RuntimeError:
                continue
            raw_searches.append(query_text)
            for score, slug, _text in _parse_search_output(output):
                matched.setdefault(slug, score)
            if len(matched) >= 20:
                break
        by_id = {event.event_id: event for event in self._events}
        items: list[RetrievedItem] = []
        seen_ids: set[str] = set()
        for event_id, score in matched.items():
            if not event_id or event_id in seen_ids:
                continue
            event = by_id.get(event_id)
            if event is None:
                continue
            if event.available_at > query.as_of or event.principal != query.principal:
                continue
            if query.scope and event.scope != query.scope:
                continue
            seen_ids.add(event_id)
            items.append(
                RetrievedItem(
                    item_id=event.event_id,
                    text=event.text,
                    score=score,
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
            raw={"terms": terms, "searches": raw_searches, "matched": len(items)},
        )

    def snapshot(self) -> ProviderSnapshot:
        files = {}
        git_dir = self.brain_dir / ".git"
        if git_dir.exists():
            proc = subprocess.run(
                ["git", "-C", str(self.brain_dir), "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if proc.returncode == 0:
                files["git_head"] = proc.stdout.strip()
        files["manifest"] = hashing.sha256_text(
            "\n".join(sorted(event.event_id for event in self._events)) or "empty"
        )
        # Logical state hash is order-independent (the git HEAD is recorded
        # in files but not part of the logical identity: fresh instances with
        # identical state must agree regardless of commit timestamps).
        state_hash = files["manifest"]
        return ProviderSnapshot(provider=self.name, state_hash=state_hash, files=files, events=tuple(self._events))

    def restore(self, snapshot: ProviderSnapshot) -> None:
        self.reset()
        if snapshot.events:
            self.ingest(list(snapshot.events))

    def export(self) -> dict:
        return {
            "format": "sovbench/gbrain-export/1",
            "gbrain_commit": GBRAIN_COMMIT,
            "events": [event.to_dict() for event in sorted(self._events, key=lambda event: event.event_id)],
            "system_of_record": "markdown+frontmatter",
        }

    def import_data(self, data) -> None:
        self.reset()
        events = [Event.from_dict(record) for record in data["events"]]
        self.ingest(events)

    def restart(self) -> None:
        pass  # state lives on disk (git brain + derived index)

    def stats(self) -> dict:
        return {
            "pages": len(self._events),
            "gbrain_commit": GBRAIN_COMMIT,
            "gbrain_bin": str(self.gbrain_bin),
        }

    def cleanup(self) -> None:
        for trash in self._trash:
            try:
                _rmtree_retry(trash, tries=3)
            except OSError:
                pass  # host file lock; trash is under data_dir and removable later
        self._trash = []


_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "do", "does",
    "did", "what", "which", "who", "whose", "where", "when", "how", "why",
    "my", "your", "his", "her", "their", "its", "our", "of", "in", "on", "at",
    "to", "for", "with", "and", "or", "not", "now", "current", "currently",
    "preferred", "favorite", "person", "people", "using", "use", "uses",
}


SEARCH_RECORD_RE = re.compile(r"^\[([0-9.eE+\-]+)\]\s+([A-Za-z0-9_.\-]+)\s+--\s+(.*)$")


def _parse_search_output(output: str) -> list[tuple[float, str, str]]:
    records = []
    for line in output.splitlines():
        match = SEARCH_RECORD_RE.match(line.strip())
        if match:
            try:
                score = float(match.group(1))
            except ValueError:
                score = None
            records.append((score, match.group(2), match.group(3)))
    return records


def _rmtree_retry(path: Path, tries: int = 8) -> None:
    """Windows may hold git object files briefly after CLI subprocesses exit;
    observed release within ~3 seconds on the pinned GBrain."""
    for attempt in range(tries):
        try:
            shutil.rmtree(path)
            return
        except PermissionError:
            if attempt == tries - 1:
                raise
            time.sleep(0.75 * (attempt + 1))


def make_gbrain(data_dir: Path | None = None, gbrain_bin: Path | str | None = None) -> GBrainProvider:
    return GBrainProvider(data_dir=data_dir, gbrain_bin=gbrain_bin)
