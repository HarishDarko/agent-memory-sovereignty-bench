"""CLI for the executable clean-room runtime probe.

Usage:
    python scripts/verify_cleanroom.py --run-id <run-id> [--out path] [--repo root]

Exit code 0 means the clean-room probe passed; 1 means it failed. Evidence is
written to runs/<run-id>/preflight/docker-runtime.json by default.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from benchmark.isolation.docker_probe import run_probe  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Executable clean-room runtime probe.")
    parser.add_argument("--run-id", required=True, help="Run id used to scope every resource (e.g. 2026-08-06-001).")
    parser.add_argument("--out", type=Path, default=None, help="Evidence JSON path (default runs/<run-id>/preflight/docker-runtime.json).")
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parent.parent, help="Repository root.")
    args = parser.parse_args()

    out = args.out
    if out is None:
        out = args.repo / "runs" / args.run_id / "preflight" / "docker-runtime.json"
    evidence = run_probe(run_id=args.run_id, repo_root=args.repo, out_path=out)
    print(json.dumps({"run_id": args.run_id, "passed": evidence["passed"], "errors": evidence["errors"]}, indent=2))
    return 0 if evidence["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
