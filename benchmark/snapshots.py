"""Provider state snapshots and query-mutation detection."""

from __future__ import annotations

from dataclasses import dataclass

from benchmark.providers import ProviderSnapshot


@dataclass
class MutationCheckResult:
    passed: bool
    before_hash: str
    after_hash: str
    details: str = ""


def check_no_mutation(before: ProviderSnapshot, after: ProviderSnapshot) -> MutationCheckResult:
    if before.provider != after.provider:
        return MutationCheckResult(False, before.state_hash, after.state_hash, "provider identity changed")
    ok = before.state_hash == after.state_hash
    details = "state unchanged" if ok else "STATE MUTATED after retrieval"
    return MutationCheckResult(ok, before.state_hash, after.state_hash, details)
