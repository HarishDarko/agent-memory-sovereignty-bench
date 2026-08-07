"""Deterministic token estimation and fixed reader-context budgeting."""

from __future__ import annotations

import math
import json
from dataclasses import dataclass, field
from typing import Iterable

from benchmark.providers import RetrievedItem


def estimate_tokens(text: str) -> int:
    """Deterministic approximation (~4 chars/token).

    Documented approximation used for budget enforcement and accounting. Swap
    for the model's real tokenizer when the real gateway mode is enabled.
    """
    if not text:
        return 0
    return max(1, math.ceil(len(text) / 4))


def truncate_to_budget(text: str, budget: int) -> tuple[str, int, bool]:
    """Return (truncated_text, tokens_used, truncated)."""
    tokens = estimate_tokens(text)
    if tokens <= budget:
        return text, tokens, False
    marker = " \u2026[truncated]"
    prefix = text[: max(0, budget * 4 - len(marker) - 8)]
    while estimate_tokens(prefix + marker) > budget and prefix:
        prefix = prefix[:-4]
    out = prefix + marker
    return out, estimate_tokens(out), True


@dataclass(frozen=True)
class EvidenceBundle:
    text: str
    tokens: int
    truncated: bool
    item_ids: tuple[str, ...]
    omitted_items: int = 0
    estimator: str = "chars-per-token-v1"


def format_evidence(items: Iterable[RetrievedItem], budget: int) -> EvidenceBundle:
    """Serialize complete evidence records and never claim omitted IDs were sent."""
    source_items = list(items)
    parts: list[str] = []
    ids: list[str] = []
    text_truncated = False
    metadata_keys = (
        "principal",
        "subject",
        "scope",
        "authority",
        "source",
        "available_at",
        "valid_from",
        "valid_to",
        "kind",
    )

    def record(item: RetrievedItem, item_text: str) -> str:
        row = {"id": item.item_id, "score": item.score}
        for key in metadata_keys:
            if key in item.metadata and item.metadata[key] is not None:
                row[key] = item.metadata[key]
        row["text"] = item_text
        return json.dumps(row, sort_keys=True, ensure_ascii=False, separators=(",", ":"))

    for item in source_items:
        encoded = record(item, item.text)
        candidate = "\n".join(parts + [encoded])
        if estimate_tokens(candidate) <= budget:
            parts.append(encoded)
            ids.append(item.item_id)
            continue

        if not parts:
            marker = "…[truncated]"
            low, high = 0, len(item.text)
            best = ""
            while low <= high:
                mid = (low + high) // 2
                shortened = item.text[:mid] + marker
                candidate_record = record(item, shortened)
                if estimate_tokens(candidate_record) <= budget:
                    best = candidate_record
                    low = mid + 1
                else:
                    high = mid - 1
            if best:
                parts.append(best)
                ids.append(item.item_id)
                text_truncated = True
        break

    joined = "\n".join(parts)
    omitted = len(source_items) - len(ids)
    return EvidenceBundle(
        text=joined,
        tokens=estimate_tokens(joined),
        truncated=text_truncated or omitted > 0,
        item_ids=tuple(ids),
        omitted_items=omitted,
    )
