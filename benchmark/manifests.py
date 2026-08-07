"""Run manifests and run artifact writing (see canonical plan section 26)."""

from __future__ import annotations

import json
import platform
import sys
from pathlib import Path

from benchmark import hashing
from benchmark.schema import SchemaError, validate_manifest


def prompt_digest(prompt_path: Path | str, version: str) -> str:
    return hashing.sha256_text(hashing.sha256_file(prompt_path) + "|" + version)


def lock_digest(repo_root: Path) -> str:
    parts: list[str] = []
    for rel in ("pyproject.toml", "uv.lock", ".python-version"):
        p = Path(repo_root) / rel
        if p.exists():
            parts.append(f"{rel}:{hashing.sha256_file(p)}")
    return hashing.sha256_text(";".join(parts)) if parts else "no-lock-files"


def next_run_id(run_root: Path, date_str: str) -> str:
    root = Path(run_root)
    root.mkdir(parents=True, exist_ok=True)
    seq_file = root / ".runseq"
    seq = 1
    if seq_file.exists():
        try:
            seq = int(seq_file.read_text(encoding="utf-8").strip()) + 1
        except ValueError:
            seq = 1
    seq_file.write_text(str(seq), encoding="utf-8")
    return f"{date_str}-{seq:03d}"


def build_manifest(
    *,
    run_id: str,
    track: str,
    settings,
    provider_name: str,
    provider_version: str,
    provider_capabilities: dict,
    control: bool,
    corpus_digest_value: str,
    corpus_split: str,
    prompt_digest_value: str,
    bench_time: str,
    preflight: dict,
    scores: dict,
    scorer_version: str,
    provider_stats: dict,
    status: str = "completed",
    status_reason: str = "",
    reader: dict | None = None,
    publication: dict | None = None,
    dataset_validation: dict | None = None,
    notes: str = "",
) -> dict:
    reader_info = dict(reader or {})
    reader_info.setdefault("provider", "unknown")
    reader_info.setdefault("requested_model", settings.model if settings.gateway_mode != "offline" else None)
    reader_info.setdefault("expected_release", getattr(settings, "model_release", None))
    reader_info.setdefault("actual_model", None)
    reader_info.setdefault("semantic_reader_validated", False)
    reader_info.update(
        {
            "mode": settings.gateway_mode,
            "prompt_version": settings.prompt_version,
            "prompt_hash": prompt_digest_value,
            "token_budget": settings.token_budget,
            "token_estimator": "chars-per-token-v1",
        }
    )
    return {
        "schema": "sovbench/manifest/1",
        "run_id": run_id,
        "status": status,
        "status_reason": status_reason,
        "track": track,
        "benchmark_time": bench_time,
        "reader": reader_info,
        "memory_provider": {
            "name": provider_name,
            "version": provider_version,
            "control": control,
            "uses_ground_truth": bool(provider_capabilities.get("uses_ground_truth")),
            "capabilities": provider_capabilities,
            "stats": provider_stats,
        },
        "corpus": {
            "split": corpus_split,
            "path": str(settings.corpus_dir),
            "hash": corpus_digest_value,
        },
        "runtime": {
            "python": platform.python_version(),
            "os": platform.platform(),
            "lock_hash": lock_digest(Path(__file__).resolve().parent.parent),
            "executable": sys.executable,
        },
        "isolation": preflight,
        "dataset_validation": dataset_validation,
        "scores": scores,
        "publication": publication or {"eligible": False, "reasons": ["publication eligibility not evaluated"]},
        "scorer_version": scorer_version,
        "notes": notes,
    }


def write_manifest(run_dir: Path, manifest: dict) -> Path:
    run_dir.mkdir(parents=True, exist_ok=True)
    try:
        validate_manifest(manifest)
    except SchemaError as exc:
        raise SchemaError(f"refusing to write invalid manifest: {exc}") from exc
    path = run_dir / "manifest.json"
    temp = path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(manifest, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    temp.replace(path)
    return path


def write_traces(run_dir: Path, traces: list[dict]) -> Path:
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "retrieval_trace.jsonl"
    temp = path.with_suffix(".jsonl.tmp")
    with open(temp, "w", encoding="utf-8") as f:
        for row in traces:
            f.write(json.dumps(row, sort_keys=True, default=str) + "\n")
    temp.replace(path)
    return path


def write_scores(run_dir: Path, scores_dict: dict) -> Path:
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "scores.json"
    temp = path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(scores_dict, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    temp.replace(path)
    return path
