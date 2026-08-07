"""Analyze completed runs: paired comparisons, failure denominators, reliability.

Usage:
    python scripts/analyze_runs.py --runs runs/run-a runs/run-b --out reports/analysis.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from benchmark.statistics import (  # noqa: E402
    all_success_rate,
    mcnemar_exact,
    paired_bootstrap,
    paired_diffs,
    pass_at_one,
)


def _load_run(run_dir: Path) -> dict | None:
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.exists():
        return None
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    traces = []
    trace_path = run_dir / "retrieval_trace.jsonl"
    if trace_path.exists():
        for line in trace_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                traces.append(json.loads(line))
    return {"manifest": manifest, "traces": traces}


def _entries_from_traces(traces: list[dict], blocks_field: str) -> list[dict]:
    entries = []
    for row in traces:
        score = row.get("score", {})
        reader = row.get("reader", {})
        entries.append(
            {
                "query_id": row.get("query_id"),
                "block": row.get(blocks_field) or row.get("principal") or "unknown",
                "reader_correct": score.get("reader_correct"),
                "chain_complete@5": score.get("chain_complete@5"),
                "evidence_precision": score.get("evidence_id_precision"),
                "retries": int(reader.get("retries", 0) or 0),
            }
        )
    return entries


def analyze(
    run_dirs: list[Path],
    seed: int = 20260805,
    resamples: int = 10_000,
    blocks_field: str = "subject",
) -> dict:
    runs: dict[str, dict] = {}
    failures = {"invalid_runs": [], "reader_error_attempts": 0}

    for run_dir in run_dirs:
        loaded = _load_run(run_dir)
        if loaded is None:
            continue
        manifest = loaded["manifest"]
        run_id = manifest["run_id"]
        status = manifest.get("status", "unknown")
        entries = _entries_from_traces(loaded["traces"], blocks_field)
        groups_by_query: dict[str, list[bool]] = {}
        for entry in entries:
            if entry["reader_correct"] is not None:
                groups_by_query.setdefault(entry["query_id"], []).append(entry["reader_correct"])
        attempt_groups = list(groups_by_query.values())
        runs[run_id] = {
            "status": status,
            "provider": manifest.get("memory_provider", {}).get("name"),
            "semantic_reader_validated": manifest.get("reader", {}).get("semantic_reader_validated", False),
            "attempts": len(entries),
            "pass_at_1": pass_at_one(attempt_groups),
            "all_success_rate": all_success_rate(attempt_groups),
        }
        if not status.startswith("completed_"):
            failures["invalid_runs"].append(run_id)
        failures["reader_error_attempts"] += sum(1 for entry in entries if entry["retries"] > 0)

    completed = [run_id for run_id, run in runs.items() if run["status"].startswith("completed_")]
    metrics = ("reader_accuracy", "chain_complete@5", "evidence_precision")
    metric_field = {
        "reader_accuracy": "reader_correct",
        "chain_complete@5": "chain_complete@5",
        "evidence_precision": "evidence_precision",
    }
    comparisons: dict[str, list[dict]] = {}
    for metric in metrics:
        pairs = []
        for index, run_a in enumerate(completed):
            for run_b in completed[index + 1 :]:
                if metric == "reader_accuracy" and not (
                    runs[run_a]["semantic_reader_validated"] and runs[run_b]["semantic_reader_validated"]
                ):
                    continue
                entries_a = _entries_from_traces(_traces_of(run_dirs, run_a), blocks_field)
                entries_b = _entries_from_traces(_traces_of(run_dirs, run_b), blocks_field)
                blocks_a: dict[str, list[float]] = {}
                blocks_b: dict[str, list[float]] = {}
                field = metric_field[metric]
                for entry in entries_a:
                    if entry[field] is not None:
                        blocks_a.setdefault(entry["block"], []).append(float(entry[field]))
                for entry in entries_b:
                    if entry[field] is not None:
                        blocks_b.setdefault(entry["block"], []).append(float(entry[field]))
                diffs = paired_diffs(blocks_a, blocks_b)
                if not diffs:
                    continue
                bootstrap = paired_bootstrap(diffs, n_resamples=resamples, seed=seed)
                by_query_a = {entry["query_id"]: entry["reader_correct"] for entry in entries_a}
                by_query_b = {entry["query_id"]: entry["reader_correct"] for entry in entries_b}
                aligned = [
                    (by_query_a[query_id], by_query_b[query_id])
                    for query_id in sorted(set(by_query_a) & set(by_query_b))
                    if by_query_a[query_id] is not None and by_query_b[query_id] is not None
                ]
                mcnemar = (
                    mcnemar_exact([a for a, _ in aligned], [b for _, b in aligned]) if aligned else None
                )
                pairs.append({"a": run_a, "b": run_b, "bootstrap": bootstrap, "mcnemar": mcnemar})
        if pairs:
            comparisons[metric] = pairs

    return {
        "seed": seed,
        "resamples": resamples,
        "blocks_field": blocks_field,
        "runs": runs,
        "comparisons": comparisons,
        "failures": failures,
    }


def _traces_of(run_dirs: list[Path], run_id: str) -> list[dict]:
    for run_dir in run_dirs:
        loaded = _load_run(run_dir)
        if loaded and loaded["manifest"]["run_id"] == run_id:
            return loaded["traces"]
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze completed benchmark runs.")
    parser.add_argument("--runs", nargs="+", required=True, help="Run directories or a parent dir to scan.")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--resamples", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=20260805)
    parser.add_argument("--blocks-field", default="subject", choices=("subject", "principal"))
    args = parser.parse_args()

    run_dirs: list[Path] = []
    for candidate in args.runs:
        path = Path(candidate)
        if (path / "manifest.json").exists():
            run_dirs.append(path)
        else:
            run_dirs.extend(sorted(path.glob("*/manifest.json")) and [p.parent for p in sorted(path.glob("*/manifest.json"))])

    report = analyze(run_dirs=run_dirs, seed=args.seed, resamples=args.resamples, blocks_field=args.blocks_field)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
