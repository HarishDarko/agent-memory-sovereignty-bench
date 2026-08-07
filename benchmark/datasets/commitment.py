"""SHA-256 pack commitments for the hidden TEST split."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def sha256_file(path: Path | str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _summary(pack_dir: Path) -> dict:
    events = queries = gold = 0
    kinds: dict[str, int] = {}
    for rel in ("events.jsonl", "queries.jsonl", "ground_truth.jsonl"):
        path = pack_dir / rel
        if not path.exists():
            raise FileNotFoundError(f"missing pack file: {path}")
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                if rel == "events.jsonl":
                    events += 1
                elif rel == "queries.jsonl":
                    queries += 1
                    kinds[json.loads(line)["kind"]] = kinds.get(json.loads(line)["kind"], 0) + 1
                else:
                    gold += 1
    return {
        "events": events,
        "queries": queries,
        "ground_truth_rows": gold,
        "kinds": dict(sorted(kinds.items())),
    }


def pack_commitment(pack_dir: Path | str) -> dict:
    pack_dir = Path(pack_dir)
    files = {
        rel: sha256_file(pack_dir / rel)
        for rel in ("events.jsonl", "queries.jsonl", "ground_truth.jsonl")
    }
    aggregate = hashlib.sha256(
        "\n".join(f"{rel}:{files[rel]}" for rel in sorted(files)).encode("utf-8")
    ).hexdigest()
    return {
        "pack": pack_dir.name,
        "files": files,
        "aggregate": "sha256:" + aggregate,
        "summary": _summary(pack_dir),
    }


def verify_pack(pack_dir: Path | str, commitment: dict) -> list[str]:
    errors: list[str] = []
    pack_dir = Path(pack_dir)
    for rel, expected in commitment.get("files", {}).items():
        path = pack_dir / rel
        if not path.exists():
            errors.append(f"{rel}: missing file")
            continue
        if sha256_file(path) != expected:
            errors.append(f"{rel}: hash mismatch")
    if pack_commitment(pack_dir)["aggregate"] != commitment.get("aggregate"):
        errors.append("aggregate hash mismatch")
    return errors


def write_commitments(commitments: dict, path: Path | str) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "sovbench/commitment/1",
        "packs": commitments,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def load_commitments(path: Path | str) -> dict:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)
