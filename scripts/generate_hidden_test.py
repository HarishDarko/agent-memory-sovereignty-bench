"""Generate the hidden TEST packs and commit only their SHA-256 commitments.

Packs land under scorer_private/test-v1/ (gitignored). The master seed is
stored next to them (gitignored); only the commitment file under
datasets/commitments/ is committed. Existing packs are never overwritten
without --force, which breaks commitment integrity.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from benchmark.datasets.commitment import pack_commitment, write_commitments  # noqa: E402
from benchmark.datasets.generator_v2 import personal_test_pack  # noqa: E402
from benchmark.config import REPO_ROOT  # noqa: E402


def _pack_seed(master_hex: str, pack_name: str) -> int:
    digest = hashlib.sha256((master_hex + "|" + pack_name).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate hidden TEST packs and their commitment.")
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "scorer_private" / "test-v1")
    parser.add_argument("--commitments", type=Path, default=REPO_ROOT / "datasets" / "commitments" / "test-v1.json")
    parser.add_argument("--packs", type=int, default=3)
    parser.add_argument("--per-pack", type=int, default=64)
    parser.add_argument("--force", action="store_true", help="regenerate existing packs (breaks prior commitment)")
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    seeds_path = out / "seeds.json"
    if seeds_path.exists():
        master_hex = json.loads(seeds_path.read_text(encoding="utf-8"))["master_seed_hex"]
    else:
        master_hex = secrets.token_hex(16)
        seeds_path.write_text(
            json.dumps(
                {
                    "schema": "sovbench/seeds/1",
                    "master_seed_hex": master_hex,
                    "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"wrote unrevealed master seed to {seeds_path} (gitignored)")

    commitments: dict[str, dict] = {}
    for index in range(1, args.packs + 1):
        pack_name = f"pack-{index}"
        pack_dir = out / pack_name
        if pack_dir.exists() and any(pack_dir.iterdir()) and not args.force:
            print(f"refusing to overwrite existing pack {pack_dir} (use --force to break commitment integrity)")
            return 1
        corpus = personal_test_pack(seed=_pack_seed(master_hex, pack_name), target=args.per_pack, set_name=pack_name)
        corpus.to_files(pack_dir)
        commitments[pack_name] = pack_commitment(pack_dir)

    write_commitments(commitments, args.commitments)
    total_queries = sum(commitment["summary"]["queries"] for commitment in commitments.values())
    print(f"wrote {args.packs} packs -> {out}")
    print(f"queries total: {total_queries}")
    print(f"commitment: {args.commitments}")
    for pack_name, commitment in commitments.items():
        kinds = commitment["summary"]["kinds"]
        print(f"  {pack_name}: {commitment['summary']['queries']} queries, {len(kinds)} kinds, aggregate {commitment['aggregate']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
