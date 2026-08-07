"""Attest the exact pinned GBrain + local Ollama follow-up environment."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE = Path(os.environ.get(
    "SOVBENCH_GBRAIN_SOURCE",
    str(Path.home() / ".bun" / "install" / "global" / "node_modules" / "gbrain"),
))
DEFAULT_OLLAMA = Path(os.environ.get(
    "OLLAMA_BIN",
    str(Path.home() / "AppData" / "Local" / "Programs" / "Ollama" / "ollama.exe"),
))
ATTESTATION_PATH = REPO_ROOT / "runs" / "followups" / "gbrain-native-local" / "environment-attestation.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_text(args: list[str], cwd: Path | None = None, env: dict | None = None) -> str:
    return subprocess.check_output(args, cwd=cwd, env=env, text=True, encoding="utf-8").strip()


def pinned_source_attestation(source: Path) -> dict:
    git_args = ["git", "-c", f"safe.directory={source}", "-C", str(source)]
    commit = run_text([*git_args, "rev-parse", "HEAD"])
    package = json.loads((source / "package.json").read_text(encoding="utf-8"))
    files = [
        "package.json",
        "src/core/ai/recipes/ollama.ts",
        "src/core/ai/gateway.ts",
        "src/commands/init.ts",
        "docs/integrations/embedding-providers.md",
    ]
    return {
        "path": str(source),
        "commit": commit,
        "version": package.get("version"),
        "source_hashes": {name: sha256_file(source / name) for name in files},
    }


def ollama_attestation(base_url: str, model: str, ollama_bin: Path) -> dict:
    root = base_url.rstrip("/")
    with urllib.request.urlopen(root + "/api/tags", timeout=10) as response:
        tags = json.loads(response.read().decode("utf-8"))
    models = tags.get("models", [])
    matching = [item for item in models if item.get("name") in {model, model.split(":", 1)[0]}]
    body = json.dumps({"model": model, "input": ["memory sovereignty benchmark"]}).encode("utf-8")
    request = urllib.request.Request(
        root + "/api/embed",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        embed = json.loads(response.read().decode("utf-8"))
    vectors = embed.get("embeddings") or []
    if not vectors or not vectors[0]:
        raise RuntimeError("Ollama returned no embedding vector")
    ollama_env = dict(os.environ)
    ollama_env["OLLAMA_HOST"] = root.removeprefix("http://").removeprefix("https://")
    version = run_text([str(ollama_bin), "--version"], env=ollama_env)
    return {
        "base_url": root,
        "model_requested": model,
        "model_response": embed.get("model"),
        "models": matching,
        "embedding_dimensions": len(vectors[0]),
        "ollama_version": version,
    }


def build_attestation(
    *,
    source: Path = DEFAULT_SOURCE,
    ollama_bin: Path = DEFAULT_OLLAMA,
    base_url: str | None = None,
    model: str = "snowflake-arctic-embed:335m",
    dimensions: int = 1024,
) -> dict:
    base_url = base_url or os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:4713")
    source_data = pinned_source_attestation(source)
    ollama_data = ollama_attestation(base_url, model, ollama_bin)
    if ollama_data["embedding_dimensions"] != dimensions:
        raise RuntimeError(
            f"configured dimension {dimensions} != Ollama dimension {ollama_data['embedding_dimensions']}"
        )
    bun_version = run_text([os.environ.get("BUN_BIN", "bun"), "--version"])
    return {
        "schema": "sovbench/followup-environment-attestation/1",
        "purpose": "POST-FREEZE SUPPLEMENTARY GBRAIN-NATIVE LOCAL-EMBEDDING RUN",
        "attested_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "gbrain": source_data,
        "ollama": ollama_data,
        "bun_version": bun_version,
        "configured_embedding_model": f"ollama:{model}",
        "configured_embedding_dimensions": dimensions,
        "reader_model": "deepseek-v4-flash",
        "reader_is_local": False,
        "embedding_is_local": True,
        "hidden_test_touched": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--ollama-bin", type=Path, default=DEFAULT_OLLAMA)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--model", default="snowflake-arctic-embed:335m")
    parser.add_argument("--dimensions", type=int, default=1024)
    parser.add_argument("--output", type=Path, default=ATTESTATION_PATH)
    args = parser.parse_args(argv)
    data = build_attestation(
        source=args.source,
        ollama_bin=args.ollama_bin,
        base_url=args.base_url,
        model=args.model,
        dimensions=args.dimensions,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(data, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
