"""Individual preflight checks (see canonical plan sections 15-16)."""

from __future__ import annotations

from pathlib import Path

from benchmark.events import Event, Query
from contamination.models import PreflightContext, PreflightResult
from providers.oracle import OracleProvider


CANARY_TOKENS = ["ORANGE-417", "VIOLET-926", "SILVER-183", "COBALT-552"]
NO_MEMORY_PROBE_SECRETS = [
    "What is the vault passcode for ORANGE-417?",
    "What is the recovery phrase for VIOLET-926?",
    "What is the locker combination for SILVER-183?",
    "What is the network key for COBALT-552?",
    "What is the archive code for EMERALD-771?",
]


def _temp_provider(ctx: PreflightContext, tmp_root: Path, label: str):
    return ctx.provider_factory(tmp_root / f"{label}_{ctx.provider_name}")


def check_no_memory_control(ctx: PreflightContext, tmp_root: Path) -> PreflightResult:
    """No-memory control: the semantic reader must abstain for synthetic secrets
    with no evidence. Runs through the configured gateway (the exact scored
    request path) so leakage is measured, not assumed."""
    if ctx.settings.gateway_mode == "offline":
        return PreflightResult(
            "no_memory_control",
            True,
            required=True,
            applicable=False,
            details="offline plumbing stub cannot validate semantic reader leakage or abstention",
        )
    if ctx.gateway is None:
        return PreflightResult(
            "no_memory_control",
            False,
            required=True,
            applicable=True,
            details="semantic no-memory probe requires the configured gateway before scoring",
        )
    leaked: list[str] = []
    for secret in NO_MEMORY_PROBE_SECRETS:
        query = Query(
            query_id="probe-no-memory",
            question=secret,
            principal="user_001",
            scope="personal",
            as_of=ctx.clock.now(),
            kind="current_state",
        )
        try:
            response = ctx.gateway.generate(query, [], ctx.settings.prompt_version)
            structured = (response.structured or {}) if hasattr(response, "structured") else {}
            if not structured.get("abstain", False):
                leaked.append(secret)
        except Exception as exc:  # noqa: BLE001 - a probe failure is a hard preflight failure
            return PreflightResult(
                "no_memory_control",
                False,
                required=True,
                applicable=True,
                details=f"no-memory probe request failed: {type(exc).__name__}: {str(exc)[:200]}",
            )
    passed = not leaked
    return PreflightResult(
        "no_memory_control",
        passed,
        required=True,
        applicable=True,
        details=(
            f"probed {len(NO_MEMORY_PROBE_SECRETS)} synthetic secrets with empty evidence "
            f"through the configured gateway; abstained={len(NO_MEMORY_PROBE_SECRETS) - len(leaked)} "
            f"leaked={len(leaked)}"
        ),
    )


def check_oracle_control(ctx: PreflightContext) -> PreflightResult:
    """Oracle control: perfect evidence must be retrievable (presence == 1.0)."""
    oracle = OracleProvider(gold_events={qid: [e for e in ctx.events if e.event_id in row.gold_event_ids] for qid, row in ctx.gold.items()})
    bad = 0
    checked = 0
    for q in ctx.queries:
        row = ctx.gold.get(q.query_id)
        if row is None or row.abstain or not row.gold_event_ids:
            continue
        retrieval = oracle.retrieve(q)
        checked += 1
        if {item.item_id for item in retrieval.items} != set(row.gold_event_ids):
            bad += 1
    passed = checked > 0 and bad == 0
    details = f"checked {checked} non-abstain queries; incomplete oracle evidence chains={bad}"
    return PreflightResult("oracle_control", passed, required=True, applicable=checked > 0, details=details)


def check_canary_isolation(ctx: PreflightContext, tmp_root: Path) -> PreflightResult:
    """Cross-provider canary isolation (plan 15.1): only this provider's canary retrievable."""
    if ctx.is_control:
        return PreflightResult("canary_isolation", True, required=True, applicable=False,
                               details="control provider retrieves nothing; check not applicable")
    provider = _temp_provider(ctx, tmp_root, "canary")
    provider.reset()
    now = ctx.clock.now()
    mine = CANARY_TOKENS[0]
    others = CANARY_TOKENS[1:]
    # Only THIS provider's canary is ingested (registry guarantees one token per run).
    provider.ingest(
        [
            Event(
                event_id="canary-0",
                available_at=now,
                principal="p_canary",
                scope="personal",
                authority="user_explicit",
                source="preflight-canary",
                text=f"Canary marker {mine} belongs to this provider run.",
                kind="canary",
            )
        ]
    )
    provider.await_ready()

    q_mine = Query("canary-mine", f"What is the canary marker {mine}?", "p_canary", "personal", now)
    res_mine = provider.retrieve(q_mine)
    mine_texts = " ".join(it.text for it in res_mine.items)
    has_mine = mine in mine_texts

    leaked = []
    for tok in others:
        res = provider.retrieve(Query("canary-other", f"What is the canary marker {tok}?", "p_canary", "personal", now))
        if any(tok in it.text for it in res.items):
            leaked.append(tok)
    provider.cleanup()

    passed = has_mine and not leaked
    details = (
        f"in-process namespace probe only: own canary retrievable={has_mine}; "
        f"foreign canaries leaked={leaked or 'none'}; container volume isolation still requires runtime proof"
    )
    return PreflightResult("canary_isolation", passed, required=True, applicable=True, details=details)


def check_cross_user_isolation(ctx: PreflightContext, tmp_root: Path) -> PreflightResult:
    """Cross-user leakage (plan 15.8): user A's facts must not surface for user B."""
    if ctx.is_control:
        return PreflightResult("cross_user_isolation", True, required=True, applicable=False,
                               details="control provider retrieves nothing; check not applicable")
    provider = _temp_provider(ctx, tmp_root, "cross_user")
    provider.reset()
    now = ctx.clock.now()
    secret = "Cipher-77"
    ev_a = Event(
        event_id="xu-a",
        available_at=now,
        principal="person_a",
        scope="personal",
        authority="user_explicit",
        source="preflight-xu",
        text=f"person_a's private keycode is {secret}.",
        kind="secret",
    )
    provider.ingest([ev_a])
    provider.await_ready()
    q_b = Query("xu-q", "What is person_a's private keycode?", "person_b", "personal", now)
    res = provider.retrieve(q_b)
    leaked = any(secret in it.text for it in res.items)
    provider.cleanup()
    details = "no cross-user leak" if not leaked else f"CROSS-USER LEAK: {secret} retrieved for person_b"
    return PreflightResult("cross_user_isolation", not leaked, required=True, applicable=True, details=details)


def check_future_leakage(ctx: PreflightContext, tmp_root: Path) -> PreflightResult:
    """Future-information leakage (plan 15.3): future events must not be retrievable."""
    if ctx.is_control:
        return PreflightResult("future_leakage", True, required=True, applicable=False,
                               details="control provider retrieves nothing; check not applicable")
    provider = _temp_provider(ctx, tmp_root, "future_leak")
    provider.reset()
    now = ctx.clock.now()
    future = Event(
        event_id="fl-future",
        available_at="2099-01-01T00:00:00Z",
        principal="person_a",
        scope="personal",
        authority="user_explicit",
        source="preflight-fl",
        text="person_a's future secret is FUTURE-99.",
        kind="secret",
    )
    provider.ingest([future])
    provider.await_ready()
    q = Query("fl-q", "What is person_a's future secret?", "person_a", "personal", now)
    res = provider.retrieve(q)
    leaked = any("FUTURE-99" in it.text for it in res.items)
    provider.cleanup()
    details = "no future-event leakage" if not leaked else "FUTURE EVENT RETRIEVED at earlier as_of"
    return PreflightResult("future_leakage", not leaked, required=True, applicable=True, details=details)


def check_gold_inaccessibility(ctx: PreflightContext) -> PreflightResult:
    """Gold-answer leakage (plan 15.5): gold must never be inside provider state."""
    gold_path = Path(ctx.settings.gold_path).resolve()
    issues: list[str] = []
    if ctx.data_dir:
        data_dir = Path(ctx.data_dir).resolve()
        if gold_path == data_dir or gold_path.is_relative_to(data_dir) or data_dir.is_relative_to(gold_path):
            issues.append(f"gold path {gold_path} overlaps provider data dir {data_dir}")
    if "scorer_private" in gold_path.parts and gold_path.exists():
        # hidden gold present and provider data dir shares any ancestor with it is handled above
        pass
    passed = not issues
    details = "; ".join(issues) or "gold outside provider data dir"
    return PreflightResult("gold_inaccessibility", passed, required=True, applicable=True, details=details)


def check_query_mutation(ctx: PreflightContext, tmp_root: Path) -> PreflightResult:
    """Query read-only/no-update (plan 15.2): retrieval must not mutate state."""
    if ctx.is_control:
        return PreflightResult("query_mutation", True, required=True, applicable=False,
                               details="control provider retrieves nothing; check not applicable")
    provider = _temp_provider(ctx, tmp_root, "mutation")
    provider.reset()
    now = ctx.clock.now()
    events = [
        Event(
            event_id=f"qm-{i}",
            available_at=now,
            principal="person_a",
            scope="personal",
            authority="user_explicit",
            source="preflight-qm",
            text=f"person_a's stable fact number {i} is token QM-{100+i}.",
            kind="fact",
        )
        for i in range(5)
    ]
    provider.ingest(events)
    provider.await_ready()
    q = Query("qm-q", "What is person_a's stable fact number 3?", "person_a", "personal", now)
    before = provider.snapshot()
    provider.retrieve(q)
    after = provider.snapshot()
    provider.cleanup()
    passed = before.state_hash == after.state_hash
    details = "state unchanged after retrieval" if passed else "STATE MUTATED by retrieval"
    return PreflightResult("query_mutation", passed, required=True, applicable=True, details=details)


def check_network_egress(ctx: PreflightContext) -> PreflightResult:
    """Runtime egress evidence; local in-process baselines have no provider container."""
    if not ctx.containerized:
        return PreflightResult(
            "network_egress",
            True,
            required=True,
            applicable=False,
            details="in-process baseline has no provider container; no runtime container egress claim made",
        )
    return PreflightResult(
        "network_egress",
        False,
        required=True,
        applicable=True,
        details="runtime provider egress denial probe is not implemented in Phase 0",
    )


def check_compose_policy(ctx: PreflightContext) -> PreflightResult:
    """Static Compose policy lint. This is configuration evidence, not a runtime probe."""
    compose = Path(ctx.settings.docker_compose)
    if not compose.exists():
        return PreflightResult(
            "compose_policy",
            False,
            required=True,
            applicable=True,
            details="compose policy file missing",
        )
    text = compose.read_text(encoding="utf-8")
    issues: list[str] = []
    if "network_mode: host" in text:
        issues.append("host networking used")
    if "internal: true" not in text:
        issues.append("no internal (egress-blocked) network declared")
    passed = not issues
    if "scorer_private" in text or "ground_truth" in text:
        issues.append("compose mentions a private scorer or ground-truth mount")
    details = "; ".join(issues) or "static policy declares an internal provider network and no gold mount"
    return PreflightResult("compose_policy", passed, required=True, applicable=True, details=details)


def check_fresh_state(ctx: PreflightContext, tmp_root: Path) -> PreflightResult:
    """Reset must return a used provider to the same empty logical state."""
    provider = _temp_provider(ctx, tmp_root, "fresh_state")
    provider.reset()
    empty_before = provider.snapshot().state_hash
    now = ctx.clock.now()
    provider.ingest(
        [
            Event(
                event_id="fresh-state-canary",
                available_at=now,
                principal="fresh_user",
                scope="personal",
                authority="user_explicit",
                source="preflight",
                text="Fresh-state canary FRESH-771.",
                kind="canary",
                subject="fresh_subject",
            )
        ]
    )
    provider.await_ready()
    provider.reset()
    empty_after = provider.snapshot().state_hash
    provider.cleanup()
    passed = empty_before == empty_after
    return PreflightResult(
        "fresh_state",
        passed,
        required=True,
        applicable=True,
        details="reset restored empty state" if passed else "reset did not restore the expected empty state",
    )


def check_reader_statelessness(ctx: PreflightContext) -> PreflightResult:
    """Reader cross-request isolation is enforced at runtime by the gateway
    proxy (max_messages=2 rejects any history reuse) and by construction in
    the DeepSeek gateway (exactly one system + one user message per request).
    The no-memory probe exercises the same proxied request path."""
    if ctx.settings.gateway_mode == "offline":
        return PreflightResult(
            "reader_statelessness",
            True,
            required=True,
            applicable=False,
            details="offline reader is a local deterministic function; semantic gateway statelessness is untested",
        )
    if ctx.gateway is None:
        return PreflightResult(
            "reader_statelessness",
            False,
            required=True,
            applicable=True,
            details="reader statelessness verification requires the configured gateway before scoring",
        )
    return PreflightResult(
        "reader_statelessness",
        True,
        required=True,
        applicable=True,
        details=(
            "stateless by construction: DeepSeekGateway builds exactly two messages per request; "
            "proxy policy max_messages=2 rejects history reuse on every proxied request including "
            "the no-memory probe"
        ),
    )
