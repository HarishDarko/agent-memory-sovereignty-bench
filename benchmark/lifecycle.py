"""Ingestion lifecycle: fresh state, future-leak filtering, freshness wait."""

from __future__ import annotations

from dataclasses import dataclass

from benchmark.clock import BenchmarkClock, events_available_by
from benchmark.events import Event
from benchmark.providers import AwaitResult, CapabilityNotSupported, MemoryProvider


class LifecycleError(RuntimeError):
    pass


@dataclass
class IngestOutcome:
    reset_ok: bool
    eligible: int
    ingested: int
    await_result: AwaitResult
    eligible_event_ids: tuple[str, ...] = ()
    lifecycle_actions: tuple[str, ...] = ()


def run_ingestion(
    provider: MemoryProvider,
    events: list[Event],
    clock: BenchmarkClock,
    timeout_s: float = 60.0,
    incremental: bool = False,
    since: str | None = None,
) -> IngestOutcome:
    """Fresh-state ingestion honoring the deterministic clock (no future events).

    ``incremental=True`` (native track) skips the per-checkpoint reset and
    ingests only events newly available since the previous checkpoint. For
    providers that apply upserts/deletes correctly the resulting state is
    identical to reset+full re-ingest, at a fraction of the cost; the
    checkpoint baseline-hash and mutation checks still verify the state.
    ``since`` is the previous checkpoint's as_of (None = first checkpoint:
    full eligible ingest without a reset).
    """
    if not incremental:
        provider.reset()
    else:
        provider.await_ready(timeout_s)
    eligible = sorted(events_available_by(events, clock.now()), key=lambda e: (e.available_at, e.event_id))
    if incremental and since:
        eligible = [
            event
            for event in eligible
            if event.available_at > since
        ]
    ingested = 0
    actions: list[str] = []
    pending: list[Event] = []

    def flush() -> None:
        nonlocal ingested
        if pending:
            ingested += provider.ingest(list(pending)).ingested
            pending.clear()

    for event in eligible:
        if event.operation == "upsert":
            pending.append(event)
            continue
        flush()
        if event.operation == "delete" and event.target_event_id:
            try:
                provider.delete(event.target_event_id)
            except CapabilityNotSupported as exc:
                raise LifecycleError(f"{provider.name} cannot execute required deletion {event.event_id}: {exc}") from exc
            actions.append(f"delete:{event.target_event_id}")
            continue
        raise LifecycleError(f"unsupported lifecycle operation {event.operation!r} in {event.event_id}")
    flush()
    await_result = provider.await_ready(timeout_s)
    if not await_result.ready:
        raise LifecycleError(f"{provider.name} not ready after ingestion: {await_result.details}")
    return IngestOutcome(
        reset_ok=True,
        eligible=len(eligible),
        ingested=ingested,
        await_result=await_result,
        eligible_event_ids=tuple(e.event_id for e in eligible),
        lifecycle_actions=tuple(actions),
    )
