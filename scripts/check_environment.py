"""Report the local environment for Phase 0 (and readiness for Phase 1)."""

from __future__ import annotations

import platform
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from benchmark.config import REPO_ROOT, load_settings  # noqa: E402


def _run(cmd: list[str]) -> tuple[bool, str]:
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return out.returncode == 0, (out.stdout or out.stderr).strip()
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def main() -> None:
    settings = load_settings()
    print(f"python: {platform.python_version()} ({sys.executable})")
    print(f"os: {platform.platform()}")

    try:
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE VIRTUAL TABLE t USING fts5(x)")
        print(f"sqlite fts5: OK (sqlite {sqlite3.sqlite_version})")
    except Exception as exc:  # noqa: BLE001
        print(f"sqlite fts5: UNAVAILABLE - {exc}")

    uv = shutil.which("uv")
    print(f"uv: {uv or 'not found (optional for host; recommended in WSL2)'}")

    ok, out = _run(["git", "rev-parse", "--show-toplevel"])
    print(f"git repo: {out if ok else 'NOT A GIT REPO'}")

    ok, out = _run(["docker", "info", "--format", "{{.ServerVersion}}"])
    print(f"docker daemon: {'reachable, version ' + out if ok else 'NOT reachable (start Docker Desktop before Phase 1)'}")

    ok, out = _run(["docker", "compose", "version", "--short"])
    print(f"docker compose: {out if ok else 'not available'}")

    ok, out = _run(["wsl", "-l", "-v"])
    print(f"wsl distros: {out if ok else 'not enumerable from this shell (may need admin / WSL service started)'}")

    corpus = settings.corpus_dir / "events.jsonl"
    print(f"dev corpus: {'present (' + str(corpus.stat().st_size) + ' bytes)' if corpus.exists() else 'MISSING - run scripts/generate_dev_corpus.py'}")
    print(f"gateway mode: {settings.gateway_mode} (model={settings.model})")
    print(f"clock start: {settings.clock_start}")
    print(f"token budget: {settings.token_budget}")


if __name__ == "__main__":
    main()
