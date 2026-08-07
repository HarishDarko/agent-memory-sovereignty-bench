"""Run the full preflight suite. Any required failure aborts the scoring run."""

from __future__ import annotations

from pathlib import Path

from contamination.checks import (
    check_canary_isolation,
    check_compose_policy,
    check_cross_user_isolation,
    check_future_leakage,
    check_gold_inaccessibility,
    check_network_egress,
    check_no_memory_control,
    check_oracle_control,
    check_query_mutation,
    check_fresh_state,
    check_reader_statelessness,
)
from contamination.models import PreflightContext, PreflightResult


def run_preflight(ctx: PreflightContext, tmp_root: Path) -> list[PreflightResult]:
    """Isolation gate. Order matters: cheap static checks first."""
    results = [
        check_network_egress(ctx),
        check_compose_policy(ctx),
        check_gold_inaccessibility(ctx),
        check_no_memory_control(ctx, tmp_root),
        check_oracle_control(ctx),
        check_canary_isolation(ctx, tmp_root),
        check_cross_user_isolation(ctx, tmp_root),
        check_future_leakage(ctx, tmp_root),
        check_query_mutation(ctx, tmp_root),
        check_fresh_state(ctx, tmp_root),
        check_reader_statelessness(ctx),
    ]
    return results


def preflight_passed(results: list[PreflightResult]) -> bool:
    return all(r.passed for r in results if r.required and r.applicable)
