"""Post-freeze GBrain adapter using a pinned local Ollama embedder.

This module is deliberately separate from ``adapter.py``. The existing V1
adapter remains the no-embedding controlled configuration. This subclass only
changes GBrain initialization and environment wiring; page storage, retrieval
normalization, snapshots, and lifecycle behavior remain the already-audited
adapter implementation.
"""

from __future__ import annotations

import os
from pathlib import Path

from providers.gbrain.adapter import GBRAIN_COMMIT, GBrainProvider


class GBrainOllamaProvider(GBrainProvider):
    """GBrain v0.42.73.2 with an explicit local Ollama embedding provider."""

    local_embedding = True

    def __init__(
        self,
        data_dir: Path | None = None,
        *,
        embedding_model: str,
        embedding_dimensions: int,
        ollama_base_url: str | None = None,
        gbrain_bin: Path | str | None = None,
        bun_bin: Path | str | None = None,
        timeout_s: float = 600.0,
    ):
        if not embedding_model or embedding_model.startswith("ollama:"):
            raise ValueError("embedding_model must be the Ollama model id, optionally including a tag")
        if embedding_dimensions <= 0:
            raise ValueError("embedding_dimensions must be positive")
        self.embedding_model = embedding_model
        self.embedding_dimensions = int(embedding_dimensions)
        self.ollama_base_url = (ollama_base_url or os.environ.get(
            "OLLAMA_BASE_URL", "http://127.0.0.1:11434/v1"
        )).rstrip("/")
        super().__init__(
            data_dir=data_dir,
            gbrain_bin=gbrain_bin,
            bun_bin=bun_bin,
            timeout_s=timeout_s,
        )

    def _env(self) -> dict:
        env = dict(os.environ)
        env["GBRAIN_HOME"] = str(self.home)
        env["OLLAMA_BASE_URL"] = self.ollama_base_url
        env["GBRAIN_EMBEDDING_MODEL"] = f"ollama:{self.embedding_model}"
        env["GBRAIN_EMBEDDING_DIMENSIONS"] = str(self.embedding_dimensions)
        env.setdefault("CI", "1")
        # Explicitly prevent accidental hosted-provider auto-detection. The
        # common DeepSeek key is not consumed by GBrain, but all embedding,
        # expansion, and chat provider keys are removed from this process.
        for key in (
            "OPENAI_API_KEY",
            "ZEROENTROPY_API_KEY",
            "VOYAGE_API_KEY",
            "GOOGLE_GENERATIVE_AI_API_KEY",
            "OPENROUTER_API_KEY",
            "ANTHROPIC_API_KEY",
            "GROQ_API_KEY",
            "TOGETHER_API_KEY",
            "MISTRAL_API_KEY",
        ):
            env.pop(key, None)
        return env

    def _ensure_brain(self) -> None:
        # This mirrors only the audited parent bootstrap. The V1 parent method
        # is intentionally not called because it hard-codes --no-embedding.
        if self.home.exists() and not (self.home / "gbrain.yml").exists() and (self.home / ".gbrain").exists():
            trash = self.data_dir / "trash-partial-gbrain-home"
            os.rename(self.home, trash)
            self._trash.append(trash)
        self.brain_dir.mkdir(parents=True, exist_ok=True)
        if not (self.brain_dir / ".git").exists():
            self._git("init", "-q")
            self._git("config", "user.name", "sovbench")
            self._git("config", "user.email", "sovbench@local")
            self._git_commit("initial brain")
        if not (self.home / "gbrain.yml").exists():
            self.home.mkdir(parents=True, exist_ok=True)
            self._run(
                "init",
                "--pglite",
                "--embedding-model",
                f"ollama:{self.embedding_model}",
                "--embedding-dimensions",
                str(self.embedding_dimensions),
                "--non-interactive",
            )
            self._run_allow_failure("sources", "remove", "default", "--confirm-destructive")
            self._run("sources", "add", "bench", "--path", str(self.brain_dir), "--force")
            self._run("sources", "default", "bench")

    def stats(self) -> dict:
        data = super().stats()
        data.update(
            {
                "provider_mode": "post-freeze-native-local-embedding",
                "embedding_model": f"ollama:{self.embedding_model}",
                "embedding_dimensions": self.embedding_dimensions,
                "ollama_base_url": self.ollama_base_url,
                "gbrain_commit": GBRAIN_COMMIT,
            }
        )
        return data


def make_gbrain_ollama(
    data_dir: Path | None = None,
    *,
    embedding_model: str,
    embedding_dimensions: int,
    ollama_base_url: str | None = None,
    gbrain_bin: Path | str | None = None,
    bun_bin: Path | str | None = None,
) -> GBrainOllamaProvider:
    return GBrainOllamaProvider(
        data_dir,
        embedding_model=embedding_model,
        embedding_dimensions=embedding_dimensions,
        ollama_base_url=ollama_base_url,
        gbrain_bin=gbrain_bin,
        bun_bin=bun_bin,
    )
