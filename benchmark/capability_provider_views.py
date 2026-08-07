"""Provider-native retrieval views used only by capability-attribution-v1."""

from __future__ import annotations

import importlib
import re
import time

from benchmark.events import Event, Query
from benchmark.providers import RetrievedItem, RetrievalResult


def _metadata(event: Event, observed: dict | None = None) -> dict:
    metadata = dict(observed or {})
    for key, value in {
        "event_id": event.event_id,
        "principal": event.principal,
        "subject": event.subject,
        "scope": event.scope,
        "authority": event.authority,
        "source": event.source,
        "available_at": event.available_at,
        "valid_from": event.valid_from,
        "valid_to": event.valid_to,
        "kind": event.kind,
    }.items():
        if value is not None:
            metadata.setdefault(key, value)
    return metadata


def native_retrieve(provider, query: Query, *, event_catalog: list[Event] | None = None) -> RetrievalResult:
    """Retrieve using the provider's tested native query surface without post-filtering."""
    view = _registered_native_view(provider.name)
    if view:
        module_name, _, function_name = view.partition(":")
        function = getattr(importlib.import_module(module_name), function_name)
        return function(provider, query, event_catalog)
    if provider.name == "gbrain":
        return _gbrain(provider, query, event_catalog)
    if provider.name == "mem0":
        return _mem0(provider, query, event_catalog)
    if provider.name == "hindsight":
        return _hindsight(provider, query, event_catalog)
    raise ValueError(f"unsupported capability-attribution provider: {provider.name}")


def _registered_native_view(name: str) -> str | None:
    """Provider-specific native-view hook declared in the provider registry.

    A Level-3 provider may implement ``native_retrieve(provider, query,
    event_catalog)`` in its adapter and reference it from the registry entry
    (``"native_view": "providers.<name>.adapter:native_retrieve"``). The
    built-in views below remain the fallback for the researched providers.
    """
    try:
        from providers.registry import registry_entry

        entry = registry_entry(name) or {}
        return entry.get("native_view")
    except Exception:
        return None


def _event_map(provider, event_catalog: list[Event] | None) -> dict[str, Event]:
    return {event.event_id: event for event in (event_catalog if event_catalog is not None else provider._events)}


def _gbrain(provider, query: Query, event_catalog: list[Event] | None) -> RetrievalResult:
    from providers.gbrain.adapter import _STOPWORDS, _parse_search_output

    started = time.perf_counter()
    terms = [term for term in re.findall(r"[a-z0-9]{2,}", query.question.lower()) if term not in _STOPWORDS][:6]
    if not terms:
        return RetrievalResult([], raw={"native_scope": "global-cli-search", "terms": []})
    searches = [" ".join(terms), *terms]
    matched: dict[str, float | None] = {}
    for query_text in searches:
        try:
            output = provider._run("search", query_text)
        except RuntimeError:
            continue
        for score, slug, _text in _parse_search_output(output):
            matched.setdefault(slug, score)
        if len(matched) >= 20:
            break
    by_id = _event_map(provider, event_catalog)
    items = [
        RetrievedItem(event_id, by_id[event_id].text, score, _metadata(by_id[event_id]))
        for event_id, score in matched.items()
        if event_id in by_id
    ]
    return RetrievalResult(
        items,
        latency_ms=round((time.perf_counter() - started) * 1000.0, 3),
        raw={"native_scope": "global-cli-search", "terms": terms, "matched": len(items)},
    )


def _mem0(provider, query: Query, event_catalog: list[Event] | None) -> RetrievalResult:
    from providers.mem0.adapter import _env_override

    started = time.perf_counter()
    memory = provider._memory_instance()
    with _env_override(provider._env()):
        result = memory.search(query=query.question, filters={"user_id": query.principal}, limit=20)
    by_id = _event_map(provider, event_catalog)
    items: list[RetrievedItem] = []
    seen: set[str] = set()
    for item in result.get("results", []):
        observed = item.get("metadata") or {}
        event_id = observed.get("event_id")
        if not event_id or event_id in seen or event_id not in by_id:
            continue
        event = by_id[event_id]
        text = item.get("memory") or item.get("text") or event.text
        score = float(item["score"]) if item.get("score") is not None else None
        items.append(RetrievedItem(event_id, text, score, _metadata(event, observed)))
        seen.add(event_id)
    return RetrievalResult(
        items,
        latency_ms=round((time.perf_counter() - started) * 1000.0, 3),
        raw={"native_scope": "user_id-filter", "total_results": len(result.get("results", [])), "matched": len(items)},
    )


def _hindsight(provider, query: Query, event_catalog: list[Event] | None) -> RetrievalResult:
    from providers.hindsight.adapter import _iter_recall_results

    started = time.perf_counter()
    result = provider._request(
        "POST",
        f"/v1/default/banks/{provider.bank_id}/memories/recall",
        {"query": query.question, "budget": "high", "max_tokens": 4096, "query_timestamp": query.as_of},
    )
    by_id = _event_map(provider, event_catalog)
    items: list[RetrievedItem] = []
    seen: set[str] = set()
    for item in _iter_recall_results(result):
        observed = item.get("metadata") or {}
        event_id = observed.get("event_id") or item.get("event_id")
        if not event_id or event_id in seen or event_id not in by_id:
            continue
        event = by_id[event_id]
        scores = item.get("scores") or {}
        score = scores.get("final") if isinstance(scores, dict) else None
        items.append(
            RetrievedItem(
                event_id,
                item.get("text") or item.get("memory") or event.text,
                float(score) if score is not None else None,
                _metadata(event, observed),
            )
        )
        seen.add(event_id)
    return RetrievalResult(
        items,
        latency_ms=round((time.perf_counter() - started) * 1000.0, 3),
        raw={"native_scope": "bank+query_timestamp", "matched": len(items)},
    )
