"""Validate and analyze Capability Attribution Ablation v1 TEST artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))

from benchmark.capability_analysis import analyze_attempts, blind_analysis, validate_test_completeness
from benchmark.capability_attribution import build_test_selection
from benchmark.config import REPO_ROOT
from benchmark.hashing import sha256_file


PROVIDERS = ("gbrain", "mem0", "hindsight")
PACKS = ("pack-1", "pack-2", "pack-3")
DEFAULT_RUN_ROOT = REPO_ROOT / "runs" / "followups" / "capability-attribution-v1" / "test"


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        raise ValueError(f"missing artifact: {path}")
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_and_validate(run_root: Path) -> tuple[list[dict], list[dict], list[dict], dict]:
    attempts: list[dict] = []
    retrievals: list[dict] = []
    deletions: list[dict] = []
    manifests = []
    for provider in PROVIDERS:
        for pack in PACKS:
            pack_dir = run_root / provider / pack
            manifest_path = pack_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest.get("status") != "completed":
                raise ValueError(f"incomplete manifest: {manifest_path}")
            hash_path = pack_dir / "manifest.sha256"
            if hash_path.read_text(encoding="utf-8").strip() != sha256_file(manifest_path):
                raise ValueError(f"manifest hash mismatch: {manifest_path}")
            manifests.append(
                {
                    "provider": provider,
                    "pack": pack,
                    "code_commit": manifest["code_commit"],
                    "protocol_hash": manifest["protocol_hash"],
                    "dataset_hashes": manifest["dataset_hashes"],
                    "attempt_rows": manifest["attempt_rows"],
                    "reader_errors": manifest["reader_errors"],
                }
            )
            attempts.extend(_read_jsonl(pack_dir / "attempts.jsonl"))
            retrievals.extend(_read_jsonl(pack_dir / "retrieval-observations.jsonl"))
            deletions.extend(_read_jsonl(pack_dir / "deletion-attribution.jsonl"))

    selected = build_test_selection(PACKS)
    validate_test_completeness(attempts, providers=PROVIDERS, packs=PACKS, selected=selected)
    expected_retrieval = sum(
        1
        for provider in PROVIDERS
        for query_id, prop in selected.items()
        if not (provider == "hindsight" and prop == "temporal")
    )
    expected_deletion = len(PROVIDERS) * sum(prop == "deletion" for prop in selected.values())
    if len(retrievals) != expected_retrieval:
        raise ValueError(f"retrieval row count {len(retrievals)} != {expected_retrieval}")
    if len(deletions) != expected_deletion:
        raise ValueError(f"deletion row count {len(deletions)} != {expected_deletion}")
    quality = {
        "schema": "sovbench/capability-attribution-data-quality/1",
        "passed": True,
        "attempt_rows": len(attempts),
        "retrieval_rows": len(retrievals),
        "deletion_rows": len(deletions),
        "reader_errors": sum(bool(row.get("reader_error")) for row in attempts),
        "manifests": manifests,
    }
    return attempts, retrievals, deletions, quality


def summarize_observations(retrievals: list[dict], deletions: list[dict]) -> dict:
    by_property: dict[str, dict] = {}
    for property_name in ("authority", "provenance", "temporal", "scope"):
        values = [row for row in retrievals if row["property"] == property_name]
        by_property[property_name] = {
            "queries": len(values),
            "retrieval_changed_by_assistance": sum(row["raw_ids"] != row["assisted_ids"] for row in values),
            "raw_evidence_items": sum(len(row["raw_ids"]) for row in values),
            "assisted_evidence_items": sum(len(row["assisted_ids"]) for row in values),
            "mutation_failures": sum(not row["mutation_passed"] for row in values),
        }
    deletion_by_provider = {}
    for provider in PROVIDERS:
        values = [row for row in deletions if row["provider"] == provider]
        deletion_by_provider[provider] = {
            "queries": len(values),
            "raw_deleted_evidence_count": sum(row["raw_deleted_evidence_count"] for row in values),
            "assisted_deleted_evidence_count": sum(row["assisted_deleted_evidence_count"] for row in values),
        }
    return {"retrieval": by_property, "deletion": deletion_by_provider}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or args.run_root / "analysis"
    attempts, retrievals, deletions, quality = load_and_validate(args.run_root)
    analysis = analyze_attempts(attempts)
    analysis["observations"] = summarize_observations(retrievals, deletions)
    analysis["data_quality"] = quality
    blinded = blind_analysis(analysis)
    _write_json(output / "data-quality.json", quality)
    _write_json(output / "analysis-blinded.json", blinded)
    _write_json(output / "analysis.json", analysis)
    (output / "analysis.sha256").write_text(sha256_file(output / "analysis.json") + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "data_quality": quality}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
