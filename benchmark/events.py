"""Event, query, and ground-truth data types plus JSONL loaders."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from benchmark.hashing import sha256_text
from benchmark.schema import SchemaError, validate_event_record, validate_ground_truth_record, validate_query_record


@dataclass(frozen=True)
class Event:
    """A single synthetic source event. Timestamps are ISO-8601 UTC ('Z')."""

    event_id: str
    available_at: str
    principal: str
    scope: str
    authority: str
    source: str
    text: str
    kind: str = "fact"
    subject: Optional[str] = None
    supersedes: Optional[str] = None
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None
    operation: str = "upsert"
    target_event_id: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "available_at": self.available_at,
            "principal": self.principal,
            "scope": self.scope,
            "authority": self.authority,
            "source": self.source,
            "text": self.text,
            "kind": self.kind,
            "subject": self.subject,
            "supersedes": self.supersedes,
            "valid_from": self.valid_from,
            "valid_to": self.valid_to,
            "operation": self.operation,
            "target_event_id": self.target_event_id,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Event":
        return cls(
            event_id=str(d["event_id"]),
            available_at=str(d["available_at"]),
            principal=str(d["principal"]),
            scope=str(d.get("scope", "personal")),
            authority=str(d.get("authority", "user_explicit")),
            source=str(d.get("source", "")),
            text=str(d["text"]),
            kind=str(d.get("kind", "fact")),
            subject=d.get("subject"),
            supersedes=d.get("supersedes"),
            valid_from=d.get("valid_from"),
            valid_to=d.get("valid_to"),
            operation=str(d.get("operation", "upsert")),
            target_event_id=d.get("target_event_id"),
        )


@dataclass(frozen=True)
class Query:
    """A benchmark question. Never carries expected answers (that is gold)."""

    query_id: str
    question: str
    principal: str
    scope: Optional[str]
    as_of: str
    kind: str = "current_state"
    subject: Optional[str] = None


@dataclass(frozen=True)
class GroundTruth:
    """Private structured gold for one query."""

    query_id: str
    answer: Optional[str] = None
    abstain: bool = False
    gold_event_ids: tuple[str, ...] = ()
    note: str = ""
    answer_type: str = "exact"  # exact | set | date | bool | quantity
    acceptable_answers: tuple[str, ...] = ()


def load_events(path: Path | str) -> list[Event]:
    out = []
    for lineno, line in _iter_jsonl_lines(path):
        record = json.loads(line)
        try:
            validate_event_record(record)
        except SchemaError as exc:
            raise SchemaError(f"{path}:{lineno}: {exc}") from exc
        out.append(Event.from_dict(record))
    return out


def load_queries(path: Path | str) -> list[Query]:
    out = []
    for lineno, line in _iter_jsonl_lines(path):
        d = json.loads(line)
        try:
            validate_query_record(d)
        except SchemaError as exc:
            raise SchemaError(f"{path}:{lineno}: {exc}") from exc
        out.append(
            Query(
                query_id=str(d["query_id"]),
                question=str(d["question"]),
                principal=str(d["principal"]),
                scope=d.get("scope"),
                as_of=str(d["as_of"]),
                kind=str(d.get("kind", "current_state")),
                subject=d.get("subject"),
            )
        )
    return out


def load_ground_truth(path: Path | str) -> dict[str, GroundTruth]:
    out = {}
    for lineno, line in _iter_jsonl_lines(path):
        d = json.loads(line)
        try:
            validate_ground_truth_record(d)
        except SchemaError as exc:
            raise SchemaError(f"{path}:{lineno}: {exc}") from exc
        row = GroundTruth(
            query_id=str(d["query_id"]),
            answer=d.get("answer"),
            abstain=bool(d.get("abstain", False)),
            gold_event_ids=tuple(d.get("gold_event_ids", [])),
            note=str(d.get("note", "")),
            answer_type=str(d.get("answer_type", "exact")),
            acceptable_answers=tuple(d.get("acceptable_answers", [])),
        )
        out[row.query_id] = row
    return out


def write_jsonl(path: Path | str, rows: list[dict]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")


def _load_jsonl(path: Path | str) -> list[dict]:
    return [json.loads(line) for _, line in _iter_jsonl_lines(path)]


def _iter_jsonl_lines(path: Path | str):
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"missing dataset file: {p}")
    with open(p, encoding="utf-8") as handle:
        for lineno, line in enumerate(handle, 1):
            line = line.strip()
            if line:
                yield lineno, line


def corpus_digest(events_path: Path | str, queries_path: Path | str, gold_path: Path | str) -> str:
    """Deterministic corpus hash recorded in run manifests."""
    parts = []
    for p in (events_path, queries_path, gold_path):
        parts.append(sha256_text(Path(p).read_text(encoding="utf-8")))
    return sha256_text("\n".join(parts))
