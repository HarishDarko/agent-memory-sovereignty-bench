"""Small deterministic hashing helpers used across the harness."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def sha256_file(path: Path | str) -> str:
    p = Path(path)
    return sha256_bytes(p.read_bytes())


def canonical_json(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def hash_dir(path: Path | str) -> str:
    """Hash of all file contents under a directory (sorted relative paths)."""
    root = Path(path)
    if not root.exists():
        return sha256_text("")
    parts: list[str] = []
    for p in sorted(root.rglob("*")):
        if p.is_file():
            parts.append(f"{p.relative_to(root).as_posix()}:{sha256_file(p)}")
    return sha256_text("\n".join(parts))
