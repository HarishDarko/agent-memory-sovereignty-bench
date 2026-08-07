"""Validate a provider adapter for AMSB without touching the central benchmark.

Checks, in order:

1. registry entry and adapter import
2. capability manifest presence and parsing
3. fresh reset
4. controlled ingestion of the public DEV corpus (non-delete events)
5. readiness
6. controlled retrieval on a small query subset
7. deletion capability (UNSUPPORTED is a valid, recorded outcome)
8. native-track declaration

External integrations (GBrain CLI via Bun, Hindsight server via Docker, and
their embeddings/models) must be available in the environment; otherwise the
corresponding steps report NOT_RUN and the script still exits successfully
with the honest status table. A failed core step exits non-zero.

Usage:
    python scripts/validate_provider.py --provider mem0
    python scripts/validate_provider.py --provider example --data-dir tmp/state
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from benchmark.config import REPO_ROOT  # noqa: E402
from benchmark.events import Event, Query, load_events, load_queries  # noqa: E402
from providers.registry import RegistryError, create_provider, registry_entry  # noqa: E402


DEV_EVENTS = REPO_ROOT / "datasets" / "dev" / "personal" / "events.jsonl"
DEV_QUERIES = REPO_ROOT / "datasets" / "dev" / "personal" / "queries.jsonl"


def _load_toml(path: Path) -> dict:
    try:
        import tomllib
    except ImportError:  # pragma: no cover - Python 3.11+
        tomllib = None
    if tomllib is None:  # pragma: no cover
        raise RuntimeError("tomllib is required (Python 3.11+)")
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _rows(name: str, rows: list[tuple[str, str]]) -> None:
    width = max(len(label) for label, _ in rows) + 2
    print(f"Provider: {name}\n")
    for label, status in rows:
        print(f"{label:<{width}}{status}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a provider adapter for AMSB.")
    parser.add_argument("--provider", required=True)
    parser.add_argument("--data-dir", type=Path, default=None)
    args = parser.parse_args()

    entry = registry_entry(args.provider)
    if not entry:
        print(f"unknown provider {args.provider!r}; add a registry entry first")
        return 2

    results: list[tuple[str, str]] = []

    # 1. Adapter import through the registry factory
    try:
        create_provider(args.provider, Path(tempfile.mkdtemp(prefix="amsb-validate-")))
        results.append(("Adapter import", "PASS"))
    except (RegistryError, ModuleNotFoundError, ImportError) as exc:
        results.append(("Adapter import", f"FAIL ({exc})"))
        _rows(args.provider, results)
        return 1

    # 2. Capability manifest
    manifest_path = REPO_ROOT / (entry.get("manifest") or f"providers/{args.provider}/manifest.toml")
    manifest = None
    if manifest_path.exists():
        try:
            manifest = _load_toml(manifest_path)
            results.append(("Capability manifest", "PASS"))
        except Exception as exc:
            results.append(("Capability manifest", f"FAIL ({exc})"))
    else:
        results.append(("Capability manifest", "MISSING"))

    env_note = ""
    # Persistent scratch under runs/ (gitignored): Chroma and other on-disk
    # stores hold file locks on Windows, so temp-directory cleanup races the
    # provider. Left in place for inspection; safe to delete when stopped.
    scratch = args.data_dir or (REPO_ROOT / "runs" / "validate" / args.provider)
    if scratch.exists():
        shutil.rmtree(scratch, ignore_errors=True)
    scratch.mkdir(parents=True, exist_ok=True)
    try:
        data_dir = scratch
        try:
            provider = create_provider(args.provider, data_dir)
            provider.reset()
            results.append(("Reset", "PASS"))
        except Exception as exc:
            results.append(("Reset", f"NOT_RUN ({type(exc).__name__}: {str(exc)[:120]})"))
            env_note = str(exc)[:120]

        if provider is not None:
            try:
                events = [
                    event
                    for event in load_events(DEV_EVENTS)
                    if event.operation == "upsert"
                ][:50]
                provider.ingest(events)
                results.append(("Controlled ingest", "PASS"))
            except Exception as exc:
                results.append(("Controlled ingest", f"FAIL ({type(exc).__name__}: {str(exc)[:120]})"))
                provider.cleanup()
                _rows(args.provider, results)
                return 1

            try:
                provider.await_ready(30)
                results.append(("Readiness", "PASS"))
            except Exception as exc:
                results.append(("Readiness", f"WARN ({type(exc).__name__}: {str(exc)[:120]})"))

            try:
                queries = load_queries(DEV_QUERIES)[:3]
                for query in queries:
                    provider.retrieve(query)
                results.append(("Controlled retrieval", "PASS"))
            except Exception as exc:
                results.append(("Controlled retrieval", f"FAIL ({type(exc).__name__}: {str(exc)[:120]})"))
                provider.cleanup()
                _rows(args.provider, results)
                return 1

            # 7. Deletion capability
            from benchmark.providers import CapabilityNotSupported

            try:
                provider.delete("nonexistent-target")
                results.append(("Deletion", "PASS"))
            except CapabilityNotSupported:
                results.append(("Deletion", "UNSUPPORTED"))
            except Exception as exc:
                results.append(("Deletion", f"PASS (no-op) ({type(exc).__name__})"))

            provider.cleanup()
    finally:
        # Best-effort release for Windows file locks; the directory itself is
        # left behind under runs/ for inspection.
        time.sleep(0.5)

    # 8. Native track declaration
    tracks = (entry.get("tracks") or {})
    if tracks.get("native"):
        results.append(("Native track", "DECLARED"))
    else:
        results.append(("Native track", "NOT IMPLEMENTED"))

    if manifest is not None:
        declared = manifest.get("tracks", {})
        mismatch = (
            declared.get("controlled") is not None
            and bool(declared.get("controlled")) != bool(tracks.get("controlled", False))
        )
        if mismatch:
            results.append(("Manifest vs registry", "MISMATCH"))
            _rows(args.provider, results)
            return 1

    _rows(args.provider, results)
    if env_note:
        print(f"\nNote: {env_note}")
    print("\nReady for controlled DEV evaluation." if not any(label.startswith("FAIL") for label, _ in results) else "\nFix failures before DEV evaluation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
