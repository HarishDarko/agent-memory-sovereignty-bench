"""Provider adapter compliance: capability outcomes, adapter metadata, and the
provider contract exercised before registration or scoring.

Capability outcomes are one of: native, adapter, unsupported, not_applicable,
failed. Unsupported capabilities are recorded as unsupported - never as a
pass and never as a zero.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from benchmark.events import Event, Query
from benchmark.schema import validate_provider_capabilities

ProviderFactory = Callable[[Path], object]

OUTCOMES = ("native", "adapter", "unsupported", "not_applicable", "failed")


@dataclass(frozen=True)
class ProviderMeta:
    name: str
    adapter_version: str
    upstream_version: str
    upstream_commit: str
    image_digest: str
    config_hash: str
    license: str
    telemetry: str = "none"
    external_dependencies: list[str] = field(default_factory=list)
    network_needs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "adapter_version": self.adapter_version,
            "upstream_version": self.upstream_version,
            "upstream_commit": self.upstream_commit,
            "image_digest": self.image_digest,
            "config_hash": self.config_hash,
            "license": self.license,
            "telemetry": self.telemetry,
            "external_dependencies": list(self.external_dependencies),
            "network_needs": list(self.network_needs),
        }


def validate_meta(meta: ProviderMeta) -> list[str]:
    errors: list[str] = []
    if not meta.name:
        errors.append("meta.name must not be empty")
    if not meta.adapter_version:
        errors.append("meta.adapter_version must not be empty")
    if not meta.upstream_version:
        errors.append("meta.upstream_version must not be empty")
    if not meta.upstream_commit:
        errors.append("meta.upstream_commit must not be empty")
    if not meta.image_digest:
        errors.append("meta.image_digest must not be empty")
    if len(meta.config_hash) != 64:
        errors.append("meta.config_hash must be a 64-char sha256 hex digest")
    if not meta.license:
        errors.append("meta.license must not be empty")
    if meta.telemetry not in ("none", "disabled", "enabled"):
        errors.append(f"meta.telemetry must be none|disabled|enabled, got {meta.telemetry!r}")
    return errors


# Tiny synthetic conformance corpus: future, cross-user, delete, authority,
# and multi-hop canaries. Never used for scoring; only for contract checks.
def conformance_corpus() -> tuple[list[Event], dict[str, set[str]]]:
    events = [
        Event("conf-current", "2026-05-01T00:00:00Z", "user_001", "personal", "user_explicit", "user",
              "person_01's preferred editor is Quill.", subject="person_01"),
        Event("conf-future", "2099-01-01T00:00:00Z", "user_001", "personal", "user_explicit", "user",
              "person_01's future secret is FUTURE-77.", subject="person_01"),
        Event("conf-other-owner", "2026-05-02T00:00:00Z", "user_002", "personal", "user_explicit", "user",
              "person_02's private keycode is Cipher-77.", subject="person_02"),
        Event("conf-authority-user", "2026-05-03T00:00:00Z", "user_001", "personal", "user_explicit", "user",
              "person_01 stated that their preferred editor is Quill.", subject="person_01"),
        Event("conf-authority-forum", "2026-05-04T00:00:00Z", "user_001", "personal", "external", "forum_post",
              "A forum post claims person_01's preferred editor is Slate.", kind="poison_attempt", subject="person_01"),
        Event("conf-relationship", "2026-05-05T00:00:00Z", "user_001", "personal", "user_explicit", "user",
              "person_01's roommate is person_02.", kind="relationship", subject="person_01"),
        Event("conf-target", "2026-05-06T00:00:00Z", "user_001", "personal", "user_explicit", "user",
              "person_02's preferred editor is Beryl.", subject="person_02"),
        Event("conf-delete-target", "2026-05-07T00:00:00Z", "user_001", "personal", "user_explicit", "user",
              "person_01 used Glyph for editor.", kind="sensitive_fact", subject="person_01"),
    ]
    expected = {
        "current": {"conf-current"},
        "future": set(),  # nothing retrievable before the future event exists
        "cross_user": {"conf-other-owner"},
        "authority": {"conf-authority-user", "conf-authority-forum"},
        "multi_hop": {"conf-relationship", "conf-target"},
    }
    return events, expected


CONFORMANCE_QUESTIONS = {
    "current": "What is person_01's preferred editor?",
    "future": "What is person_01's future secret?",
    "cross_user": "What is person_02's private keycode?",
    "authority": "What is person_01's preferred editor?",
    "multi_hop": "What editor does person_01's roommate prefer?",
    "deleted": "What editor did person_01 use?",
}


def _check(outcome: str, details: str) -> dict:
    return {"outcome": outcome, "details": details}


def run_contract(meta: ProviderMeta, factory: ProviderFactory, data_dir: Path, settings=None) -> dict:
    """Exercise the adapter contract. Any 'failed' outcome fails the contract."""
    checks: dict[str, dict] = {}
    errors = validate_meta(meta)
    if errors:
        checks["meta"] = _check("failed", "; ".join(errors))
        return {"provider": meta.name, "passed": False, "checks": checks}
    checks["meta"] = _check("native", "adapter metadata valid")

    provider = factory(data_dir)
    events, canaries = conformance_corpus()
    query = lambda: Query("conf-q", CONFORMANCE_QUESTIONS["current"], "user_001", "personal", "2026-07-01T00:00:00Z")  # noqa: E731

    try:
        # Fresh state.
        provider.reset()
        fresh = provider.snapshot().state_hash
        provider.ingest(events)
        provider.await_ready()
        provider.reset()
        after_reset = provider.snapshot().state_hash
        checks["fresh_state"] = _check(
            "native" if fresh == after_reset else "failed",
            "reset restores empty state" if fresh == after_reset else "reset did not restore empty state",
        )

        # Deduplication.
        provider.ingest(events)
        result = provider.ingest(events[:2])
        checks["dedup"] = _check(
            "native" if result.ingested == 0 else "failed",
            f"re-ingesting identical events ingested {result.ingested}",
        )

        # Order-independent logical state.
        provider_a = factory(data_dir / "order-a")
        provider_b = factory(data_dir / "order-b")
        provider_a.ingest(events)
        provider_b.ingest(list(reversed(events)))
        checks["ordering"] = _check(
            "native" if provider_a.snapshot().state_hash == provider_b.snapshot().state_hash else "failed",
            "logical state hash is order-independent" if provider_a.snapshot().state_hash == provider_b.snapshot().state_hash
            else "logical state hash depends on ingestion order",
        )

        # Readiness.
        ready = provider.await_ready(timeout_s=30)
        checks["readiness"] = _check("native" if ready.ready else "failed", f"ready={ready.ready} method={ready.method}")

        # Retrieval: raw trace, current canary.
        retrieval = provider.retrieve(query())
        checks["raw_trace"] = _check("native" if isinstance(retrieval.raw, dict) else "failed", "raw trace present")
        current_ids = {item.item_id for item in provider.retrieve(query()).items}
        checks["canary_current"] = _check(
            "native" if canaries["current"] <= current_ids else "failed",
            f"current canary missing: {sorted(canaries['current'] - current_ids)}",
        )

        # Read-only retrieval.
        before = provider.snapshot().state_hash
        provider.retrieve(query())
        after = provider.snapshot().state_hash
        checks["read_only_retrieval"] = _check(
            "native" if before == after else "failed",
            "state unchanged after retrieval" if before == after else "STATE MUTATED by retrieval",
        )

        # Logical snapshot/restore.
        snapshot = provider.snapshot()
        provider.restore(snapshot)
        restored = provider.retrieve(query())
        checks["snapshot_restore"] = _check(
            "native" if {item.item_id for item in restored.items} == current_ids else "failed",
            "restore reproduces identical retrieval" if {item.item_id for item in restored.items} == current_ids
            else "restore changed retrieval results",
        )

        # Canaries: future, cross-user, authority, multi-hop, deleted.
        future_ids = {item.item_id for item in provider.retrieve(
            Query("conf-f", CONFORMANCE_QUESTIONS["future"], "user_001", "personal", "2026-06-01T00:00:00Z")
        ).items}
        checks["canary_future"] = _check(
            "native" if "conf-future" not in future_ids else "failed",
            "future event excluded at earlier as-of" if "conf-future" not in future_ids else "FUTURE EVENT RETRIEVED",
        )
        cross_ids = {item.item_id for item in provider.retrieve(
            Query("conf-x", CONFORMANCE_QUESTIONS["cross_user"], "user_002", "personal", "2026-07-01T00:00:00Z")
        ).items}
        checks["canary_cross_user"] = _check(
            "native" if cross_ids == canaries["cross_user"] else "failed",
            f"cross-user retrieval={sorted(cross_ids)}",
        )
        authority_ids = {item.item_id for item in provider.retrieve(query()).items}
        authority_user_ids = {
            item.item_id
            for item in provider.retrieve(
                Query("conf-au", "What editor does person_01 state they prefer?", "user_001", "personal", "2026-07-01T00:00:00Z")
            ).items
        }
        authority_forum_ids = {
            item.item_id
            for item in provider.retrieve(
                Query("conf-af", "Which forum post mentions person_01's preferred editor?", "user_001", "personal", "2026-07-01T00:00:00Z")
            ).items
        }
        checks["canary_authority"] = _check(
            "native"
            if "conf-authority-user" in authority_user_ids
            and "conf-authority-forum" in authority_forum_ids
            else "failed",
            f"authoritative page reachable={'conf-authority-user' in authority_user_ids}; "
            f"conflicting page reachable={'conf-authority-forum' in authority_forum_ids}",
        )
        multi_ids = {item.item_id for item in provider.retrieve(
            Query("conf-m", CONFORMANCE_QUESTIONS["multi_hop"], "user_001", "personal", "2026-07-01T00:00:00Z")
        ).items}
        checks["canary_multi_hop"] = _check(
            "native" if canaries["multi_hop"] <= multi_ids else "failed",
            f"multi-hop chain missing: {sorted(canaries['multi_hop'] - multi_ids)}",
        )
        if provider.capabilities.supports_delete:
            provider.delete("conf-delete-target")
            deleted_ids = {item.item_id for item in provider.retrieve(query()).items}
            checks["canary_deleted"] = _check(
                "native" if "conf-delete-target" not in deleted_ids else "failed",
                "deleted event excluded after delete" if "conf-delete-target" not in deleted_ids
                else "DELETED EVENT RETRIEVED",
            )
        else:
            checks["canary_deleted"] = _check(
                "not_applicable", "adapter declares no delete capability (append-only provider)"
            )

        # Error normalization.
        if provider.capabilities.supports_delete:
            try:
                provider.delete("missing-id")
                checks["error_normalization"] = _check("native", "delete of missing id handled gracefully")
            except Exception as exc:  # noqa: BLE001
                checks["error_normalization"] = _check("failed", f"delete of missing id raised {type(exc).__name__}")
        else:
            checks["error_normalization"] = _check("not_applicable", "delete capability absent")

        unknown = provider.retrieve(
            Query("conf-u", CONFORMANCE_QUESTIONS["current"], "no_such_user", "personal", "2026-07-01T00:00:00Z")
        )
        checks["unknown_principal"] = _check(
            "native" if not unknown.items else "failed",
            "unknown principal returns nothing" if not unknown.items else "unknown principal leaked items",
        )

        # Export/import.
        capabilities = provider.capabilities
        if capabilities.supports_export and capabilities.supports_import:
            try:
                pre_export_ids = {item.item_id for item in provider.retrieve(query()).items}
                exported = provider.export()
                provider.reset()
                provider.import_data(exported)
                after_import = {item.item_id for item in provider.retrieve(query()).items}
                checks["export_import"] = _check(
                    "native" if pre_export_ids == after_import else "failed",
                    "export/import round-trip" if pre_export_ids == after_import else "export/import changed state",
                )
            except Exception as exc:  # noqa: BLE001
                checks["export_import"] = _check("failed", f"export/import raised {type(exc).__name__}")
        else:
            checks["export_import"] = _check("unsupported", "adapter declares no export/import capability")

        # Restart.
        if capabilities.supports_restart:
            try:
                pre_restart_ids = {item.item_id for item in provider.retrieve(query()).items}
                provider.restart()
                restarted_ids = {item.item_id for item in provider.retrieve(query()).items}
                checks["restart"] = _check(
                    "native" if pre_restart_ids == restarted_ids else "failed",
                    "state persists across restart" if pre_restart_ids == restarted_ids else "restart lost state",
                )
            except Exception as exc:  # noqa: BLE001
                checks["restart"] = _check("failed", f"restart raised {type(exc).__name__}")
        else:
            checks["restart"] = _check("unsupported", "adapter declares no restart capability")

        # Stats and cleanup.
        stats = provider.stats()
        checks["stats"] = _check("native" if isinstance(stats, dict) else "failed", f"stats keys: {sorted(stats)}")
        provider.cleanup()
        checks["cleanup"] = _check("native", "cleanup completed")
    except Exception as exc:  # noqa: BLE001
        checks["contract_execution"] = _check("failed", f"{type(exc).__name__}: {exc}")

    failed = [name for name, check in checks.items() if check["outcome"] == "failed"]
    return {"provider": meta.name, "passed": not failed, "checks": checks, "failed_checks": failed}


def config_hash_of(config_path: Path | str | None, fallback: str) -> str:
    if config_path and Path(config_path).exists():
        return hashlib.sha256(Path(config_path).read_bytes()).hexdigest()
    return hashlib.sha256(fallback.encode("utf-8")).hexdigest()
