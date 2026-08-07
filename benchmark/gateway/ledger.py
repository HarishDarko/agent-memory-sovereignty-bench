"""Hash-chained request ledger for the model gateway.

Every request and response is recorded as a JSONL entry whose hash chains to
the previous entry. Entries store hashes and identity/usage fields only; API
keys and raw request/response content are never written.
"""

from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path

GENESIS = "GENESIS"


def _canonical(entry: dict) -> str:
    return json.dumps(
        {key: value for key, value in entry.items() if key not in ("entry_hash", "prev_hash")},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


class Ledger:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def append(self, entry: dict) -> str:
        with self._lock:
            previous = self._last_hash()
            payload = _canonical(entry) + "|" + previous
            entry_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
            record = dict(entry)
            record["prev_hash"] = previous
            record["entry_hash"] = entry_hash
            with open(self.path, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, sort_keys=True, default=str) + "\n")
            return entry_hash

    def _last_hash(self) -> str:
        if not self.path.exists() or self.path.stat().st_size == 0:
            return GENESIS
        lines = [line for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]
        return json.loads(lines[-1])["entry_hash"]

    def verify(self) -> list[str]:
        """Return chain-integrity errors; an empty list means the chain is intact."""
        errors: list[str] = []
        if not self.path.exists() or self.path.stat().st_size == 0:
            return errors
        lines = [line for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]
        previous = GENESIS
        for index, line in enumerate(lines, 1):
            try:
                entry = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"line {index}: invalid JSON: {exc}")
                continue
            if entry.get("prev_hash") != previous:
                errors.append(f"line {index}: prev_hash mismatch")
            expected = hashlib.sha256(
                (_canonical(entry) + "|" + entry.get("prev_hash", "")).encode("utf-8")
            ).hexdigest()
            if entry.get("entry_hash") != expected:
                errors.append(f"line {index}: entry_hash mismatch")
            previous = entry.get("entry_hash", "")
        return errors
