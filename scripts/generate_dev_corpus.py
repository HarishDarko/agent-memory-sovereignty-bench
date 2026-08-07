"""Generate the deterministic public DEV corpus (events, queries, ground truth)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from benchmark.config import REPO_ROOT  # noqa: E402
from benchmark.datasets.generator_v2 import generate_personal  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the public DEV corpus.")
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "datasets" / "dev" / "personal")
    parser.add_argument("--seed", type=int, default=20260805)
    parser.add_argument("--persons", type=int, default=8)
    parser.add_argument("--noise", type=int, default=24)
    args = parser.parse_args()

    corpus = generate_personal(seed=args.seed, n_persons=args.persons, n_noise=args.noise)
    corpus.to_files(args.out)
    print(f"wrote {len(corpus.events)} events, {len(corpus.queries)} queries, "
          f"{len(corpus.gold)} ground-truth rows to {args.out}")


if __name__ == "__main__":
    main()
