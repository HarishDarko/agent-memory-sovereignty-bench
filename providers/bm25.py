"""BM25 baselines: SQLite FTS5 (primary) and a pure-Python BM25 cross-check."""

from __future__ import annotations

import json
import math
import re
import sqlite3
import time
from collections import Counter
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

STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "do", "does",
    "did", "what", "which", "who", "whose", "where", "when", "how", "why",
    "my", "your", "his", "her", "their", "its", "our", "of", "in", "on", "at",
    "to", "for", "with", "and", "or", "not", "currently", "now", "main",
    "preferred", "favorite", "person", "people", "using", "use", "uses", "used",
}

TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return [t for t in TOKEN_RE.findall(text.lower()) if len(t) >= 2 and t not in STOPWORDS]


def build_fts_query(question: str, max_terms: int = 8, mode: str = "and") -> str:
    terms = tokenize(question)[:max_terms]
    if not terms:
        return ""
    if mode == "or":
        return " OR ".join(f'"{t}"' for t in terms)
    return " ".join(f'"{t}"' for t in terms)


_SCHEMA = """
CREATE TABLE events (
  rowid INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id TEXT UNIQUE NOT NULL,
  text TEXT NOT NULL,
  principal TEXT NOT NULL,
  scope TEXT NOT NULL,
  available_at TEXT NOT NULL,
  authority TEXT NOT NULL,
  source TEXT NOT NULL,
  kind TEXT NOT NULL
  ,subject TEXT
);
CREATE VIRTUAL TABLE events_fts USING fts5(text, content='events', content_rowid='rowid');
"""


class SqliteFtsProvider(MemoryProvider):
    """Boring deterministic baseline: SQLite FTS5 with bm25 ranking, scoped."""

    name = "bm25-sqlite-fts"
    version = "0.1.0"
    capabilities = Capabilities(
        supports_snapshot=True,
        supports_restore=True,
        supports_delete=True,
        read_only_retrieval=True,
    )

    def __init__(self, data_dir: Path, k: int = 10):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.data_dir / "index.sqlite3"
        self.k = k
        self._events: list[Event] = []
        self._seen: set[str] = set()
        self.reset()  # fresh schema on construction

    def reset(self) -> None:
        if self.db_path.exists():
            self.db_path.unlink()
        conn = sqlite3.connect(self.db_path)
        conn.executescript(_SCHEMA)
        conn.commit()
        conn.close()
        self._events = []
        self._seen = set()

    def ingest(self, events: list[Event]) -> IngestResult:
        conn = sqlite3.connect(self.db_path)
        try:
            ingested = 0
            for e in events:
                if e.event_id in self._seen:
                    continue
                cur = conn.execute(
                    "INSERT INTO events (event_id, text, principal, scope, available_at, authority, source, kind, subject)"
                    " VALUES (?,?,?,?,?,?,?,?,?)",
                    (e.event_id, e.text, e.principal, e.scope, e.available_at, e.authority, e.source, e.kind, e.subject),
                )
                conn.execute("INSERT INTO events_fts (rowid, text) VALUES (?,?)", (cur.lastrowid, e.text))
                self._seen.add(e.event_id)
                self._events.append(e)
                ingested += 1
            conn.commit()
        finally:
            conn.close()
        return IngestResult(ingested=ingested, latency_ms=0.0, details={"deduplicated": len(events) - ingested})

    def delete(self, target: str) -> bool:
        conn = sqlite3.connect(self.db_path)
        try:
            row = conn.execute("SELECT rowid FROM events WHERE event_id = ?", (target,)).fetchone()
            if row is None:
                return False
            conn.execute("DELETE FROM events_fts WHERE rowid = ?", (row[0],))
            conn.execute("DELETE FROM events WHERE event_id = ?", (target,))
            conn.commit()
        finally:
            conn.close()
        self._events = [event for event in self._events if event.event_id != target]
        self._seen.discard(target)
        return True

    def await_ready(self, timeout_s: float = 60.0) -> AwaitResult:
        return AwaitResult(ready=True, time_to_ready_ms=0.0, method="sync")

    def retrieve(self, query: Query) -> RetrievalResult:
        t0 = time.perf_counter()
        items: list[RetrievedItem] = []
        raw: dict = {}
        if self.db_path.exists():
            # Strict AND first; relax to OR only when nothing matched (better
            # abstention behavior for the boring baseline).
            and_q = build_fts_query(query.question, mode="and")
            or_q = build_fts_query(query.question, mode="or")
            for mode, fts_q in (("and", and_q), ("or", or_q)):
                if not fts_q:
                    continue
                rows = self._search(fts_q, query)
                raw["fts_query"] = fts_q
                raw["fts_mode"] = mode
                items = rows
                if rows:
                    break
        latency = (time.perf_counter() - t0) * 1000.0
        return RetrievalResult(items=items, latency_ms=latency, raw=raw)

    def _search(self, fts_q: str, query: Query) -> list[RetrievedItem]:
        items: list[RetrievedItem] = []
        if self.db_path.exists():
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute("PRAGMA query_only = ON")  # read-only enforcement
                sql = (
                    "SELECT e.event_id, e.text, e.principal, e.scope, e.available_at, e.authority, e.source,"
                    " e.kind, e.subject, bm25(events_fts) AS rank"
                    " FROM events_fts f JOIN events e ON e.rowid = f.rowid"
                    " WHERE events_fts MATCH ? AND e.available_at <= ? AND e.principal = ?"
                )
                params: list = [fts_q, query.as_of, query.principal]
                if query.scope:
                    sql += " AND e.scope = ?"
                    params.append(query.scope)
                sql += " ORDER BY rank LIMIT ?"
                params.append(self.k)
                for row in conn.execute(sql, params):
                    event_id, text, principal, scope, available_at, authority, source, kind, subject, rank = row
                    items.append(
                        RetrievedItem(
                            item_id=event_id,
                            text=text,
                            score=round(-float(rank), 6),
                            metadata={
                                "principal": principal,
                                "scope": scope,
                                "available_at": available_at,
                                "authority": authority,
                                "source": source,
                                "kind": kind,
                                "subject": subject,
                                "valid_from": next((e.valid_from for e in self._events if e.event_id == event_id), None),
                                "valid_to": next((e.valid_to for e in self._events if e.event_id == event_id), None),
                            },
                        )
                    )
            finally:
                conn.close()
        return items

    def snapshot(self) -> ProviderSnapshot:
        files = {}
        if self.db_path.exists():
            files["index.sqlite3"] = hashing.sha256_file(self.db_path)
        logical = [event.to_dict() for event in sorted(self._events, key=lambda event: event.event_id)]
        state_hash = hashing.sha256_text(json.dumps(logical, sort_keys=True))
        return ProviderSnapshot(provider=self.name, state_hash=state_hash, files=files, events=tuple(self._events))

    def restore(self, snapshot: ProviderSnapshot) -> None:
        """Rebuild from baseline events (clone-per-query isolation for Phase 0)."""
        self.reset()
        if snapshot.events:
            self.ingest(list(snapshot.events))

    def stats(self) -> dict:
        return {"events_indexed": len(self._events), "db_bytes": self.db_path.stat().st_size if self.db_path.exists() else 0}

    def cleanup(self) -> None:
        pass  # keep index for inspection; run dir removal cleans up


class PureBm25Provider(MemoryProvider):
    """Pure-Python BM25 (k1=1.5, b=0.75) as an independent cross-check baseline."""

    name = "bm25-pure"
    version = "0.1.0"
    capabilities = Capabilities(
        supports_snapshot=True,
        supports_restore=True,
        supports_delete=True,
        read_only_retrieval=True,
    )

    def __init__(self, data_dir: Path, k: int = 10, k1: float = 1.5, b: float = 0.75):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.k = k
        self.k1 = k1
        self.b = b
        self._docs: list[tuple[Event, list[str]]] = []
        self._df: Counter = Counter()
        self._avgdl = 0.0

    def reset(self) -> None:
        self._docs = []
        self._df = Counter()
        self._avgdl = 0.0

    def ingest(self, events: list[Event]) -> IngestResult:
        existing = {event.event_id: event for event, _ in self._docs}
        for event in events:
            existing.setdefault(event.event_id, event)
        return self._rebuild(list(existing.values()), reported_ingested=len(existing) - len(self._docs))

    def _rebuild(self, events: list[Event], reported_ingested: int | None = None) -> IngestResult:
        seen: set[str] = set()
        docs: list[tuple[Event, list[str]]] = []
        for e in events:
            if e.event_id in seen:
                continue
            seen.add(e.event_id)
            docs.append((e, tokenize(e.text)))
        self._docs = docs
        df: Counter = Counter()
        lengths = []
        for _, toks in docs:
            for t in set(toks):
                df[t] += 1
            lengths.append(len(toks))
        self._df = df
        self._avgdl = sum(lengths) / len(lengths) if lengths else 0.0
        return IngestResult(ingested=len(docs) if reported_ingested is None else reported_ingested, latency_ms=0.0)

    def await_ready(self, timeout_s: float = 60.0) -> AwaitResult:
        return AwaitResult(ready=True, time_to_ready_ms=0.0, method="sync")

    def delete(self, target: str) -> bool:
        before = len(self._docs)
        retained = [event for event, _ in self._docs if event.event_id != target]
        self._rebuild(retained)
        return len(retained) != before

    def retrieve(self, query: Query) -> RetrievalResult:
        t0 = time.perf_counter()
        terms = tokenize(query.question)
        n = len(self._docs)
        scored: list[tuple[float, Event]] = []
        for e, toks in self._docs:
            if e.available_at > query.as_of or e.principal != query.principal:
                continue
            if query.scope and e.scope != query.scope:
                continue
            s = self._score_doc(toks, terms, n)
            if s > 0:
                scored.append((s, e))
        scored.sort(key=lambda x: x[0], reverse=True)
        items = [
            RetrievedItem(
                item_id=e.event_id,
                text=e.text,
                score=round(s, 6),
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
            for s, e in scored[: self.k]
        ]
        latency = (time.perf_counter() - t0) * 1000.0
        return RetrievalResult(items=items, latency_ms=latency, raw={"terms": terms})

    def _score_doc(self, toks: list[str], terms: list[str], n: int) -> float:
        if not toks or not terms:
            return 0.0
        tf = Counter(toks)
        total = 0.0
        for t in set(terms):
            freq = tf.get(t, 0)
            if freq == 0:
                continue
            df = self._df.get(t, 0)
            idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
            denom = freq + self.k1 * (1 - self.b + self.b * (len(toks) / self._avgdl if self._avgdl else 1.0))
            total += idf * freq * (self.k1 + 1) / denom
        return total

    def snapshot(self) -> ProviderSnapshot:
        state = json.dumps(
            sorted((e.event_id, e.text, e.available_at, e.principal, e.scope) for e, _ in self._docs),
            sort_keys=True,
        )
        return ProviderSnapshot(
            provider=self.name,
            state_hash=hashing.sha256_text(state),
            files={},
            events=tuple(e for e, _ in self._docs),
        )

    def restore(self, snapshot: ProviderSnapshot) -> None:
        self.reset()
        if snapshot.events:
            self.ingest(list(snapshot.events))

    def stats(self) -> dict:
        return {"events_indexed": len(self._docs)}

    def cleanup(self) -> None:
        pass
