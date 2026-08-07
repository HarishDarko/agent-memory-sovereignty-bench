"""Split-hygiene audit: commitments, overlaps, and category balance."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from benchmark.config import REPO_ROOT  # noqa: E402
from benchmark.datasets.commitment import load_commitments, verify_pack  # noqa: E402
from benchmark.events import load_events, load_ground_truth, load_queries  # noqa: E402
from benchmark.validation import validate_split_isolation  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit DEV/TEST split hygiene.")
    parser.add_argument("--dev", type=Path, default=REPO_ROOT / "datasets" / "dev" / "personal")
    parser.add_argument("--test-root", type=Path, default=REPO_ROOT / "scorer_private" / "test-v1")
    parser.add_argument("--commitments", type=Path, default=REPO_ROOT / "datasets" / "commitments" / "test-v1.json")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    errors: list[str] = []
    warnings: list[str] = []
    dev_events = load_events(args.dev / "events.jsonl")
    dev_queries = load_queries(args.dev / "queries.jsonl")
    dev_gold = load_ground_truth(args.dev / "ground_truth.jsonl")

    commitments = load_commitments(args.commitments)
    packs: dict[str, dict] = {}
    for pack_name, commitment in commitments["packs"].items():
        pack_dir = args.test_root / pack_name
        if not pack_dir.exists():
            errors.append(f"{pack_name}: pack directory missing")
            continue
        pack_errors = verify_pack(pack_dir, commitment)
        errors.extend(f"{pack_name}: {error}" for error in pack_errors)
        packs[pack_name] = {
            "events": load_events(pack_dir / "events.jsonl"),
            "queries": load_queries(pack_dir / "queries.jsonl"),
            "gold": load_ground_truth(pack_dir / "ground_truth.jsonl"),
        }

    pack_names = list(packs)
    for index, pack_name in enumerate(pack_names):
        pack = packs[pack_name]
        result = validate_split_isolation(
            dev_events=dev_events,
            dev_queries=dev_queries,
            dev_gold=dev_gold,
            test_events=pack["events"],
            test_queries=pack["queries"],
            test_gold=pack["gold"],
        )
        errors.extend(f"{pack_name}: {error}" for error in result.errors)
        warnings.extend(f"{pack_name}: {warning}" for warning in result.warnings)
        for other_name in pack_names[index + 1 :]:
            other = packs[other_name]
            cross = validate_split_isolation(
                dev_events=pack["events"],
                dev_queries=pack["queries"],
                dev_gold=pack["gold"],
                test_events=other["events"],
                test_queries=other["queries"],
                test_gold=other["gold"],
            )
            errors.extend(f"{pack_name} x {other_name}: {error}" for error in cross.errors)

    report = {
        "schema": "sovbench/audit/1",
        "dev": {
            "events": len(dev_events),
            "queries": len(dev_queries),
            "ground_truth_rows": len(dev_gold),
        },
        "packs": {
            name: {
                "events": len(pack["events"]),
                "queries": len(pack["queries"]),
                "kinds": _kind_counts(pack["queries"]),
                "subjects": _subject_counts(pack["queries"]),
            }
            for name, pack in packs.items()
        },
        "errors": errors,
        "warnings": warnings,
        "passed": not errors,
    }
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if not errors else 1


def _kind_counts(queries) -> dict:
    counts: dict[str, int] = {}
    for query in queries:
        counts[query.kind] = counts.get(query.kind, 0) + 1
    return dict(sorted(counts.items()))


def _subject_counts(queries) -> dict:
    counts: dict[str, int] = {}
    for query in queries:
        key = query.subject or "none"
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


if __name__ == "__main__":
    raise SystemExit(main())
