"""Check and register a provider adapter against the compliance contract.

Usage:
    python scripts/check_provider.py --provider bm25-sqlite-fts

Registration is refused unless the adapter metadata validates, the provider
contract passes, and (for containerized providers) the clean-room probe
passes.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from benchmark.config import REPO_ROOT  # noqa: E402
from providers.bm25 import PureBm25Provider, SqliteFtsProvider  # noqa: E402
from providers.compliance import ProviderMeta, config_hash_of  # noqa: E402
from providers.full_context import FullContextProvider  # noqa: E402
from providers.no_memory import NoMemoryProvider  # noqa: E402
from providers.oracle import OracleProvider  # noqa: E402
from providers.registry import Registry  # noqa: E402

BUILTIN_FACTORIES = {
    "no-memory": lambda data_dir: NoMemoryProvider(data_dir),
    "oracle": lambda data_dir: OracleProvider({}, data_dir),
    "bm25-sqlite-fts": lambda data_dir: SqliteFtsProvider(data_dir, k=10),
    "bm25-pure": lambda data_dir: PureBm25Provider(data_dir, k=10),
    "full-context": lambda data_dir: FullContextProvider(data_dir),
}

CONTROLS = {"no-memory", "oracle"}


def _builtin_meta(name: str) -> ProviderMeta:
    config_path = REPO_ROOT / "config" / "providers" / f"{name}.toml"
    config_hash = config_hash_of(config_path, fallback=name)
    return ProviderMeta(
        name=name,
        adapter_version="0.1.0",
        upstream_version="0.1.0 (local baseline)",
        upstream_commit="n/a-local",
        image_digest="n/a-local",
        config_hash=config_hash,
        license="MIT",
        telemetry="none",
        external_dependencies=[],
        network_needs=[],
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Check and register a provider adapter.")
    parser.add_argument("--provider", required=True)
    parser.add_argument("--registry", type=Path, default=REPO_ROOT / "providers" / "registry.json")
    parser.add_argument("--containerized", action="store_true")
    parser.add_argument("--data-dir", type=Path, default=None)
    args = parser.parse_args()

    if args.provider not in BUILTIN_FACTORIES:
        print(f"unknown builtin provider {args.provider!r}; known: {sorted(BUILTIN_FACTORIES)}")
        return 2
    meta = _builtin_meta(args.provider)
    factory = BUILTIN_FACTORIES[args.provider]
    if args.provider in CONTROLS:
        print(f"[{args.provider}] is a control provider and is intentionally NOT registered")
        return 0

    with tempfile.TemporaryDirectory(prefix="sovbench-contract-") as tmp:
        data_dir = args.data_dir or Path(tmp)
        registry = Registry(args.registry)
        result = registry.register(meta, factory, containerized=args.containerized, data_dir=data_dir)
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0 if result.get("registered") else 1


if __name__ == "__main__":
    raise SystemExit(main())
