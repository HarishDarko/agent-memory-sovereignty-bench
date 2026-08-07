"""Static/unit checks for the post-freeze GBrain Ollama adapter."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from providers.gbrain.adapter import GBrainProvider
from providers.gbrain.local_ollama import GBrainOllamaProvider


class TestGBrainOllamaProvider(unittest.TestCase):
    def test_initializes_pinned_cli_with_explicit_local_embedding(self):
        run_calls: list[tuple[str, ...]] = []

        def fake_run(self, *args, **kwargs):
            run_calls.append(tuple(str(arg) for arg in args))
            return ""

        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(GBrainOllamaProvider, "_git", return_value=""), patch.object(
                GBrainOllamaProvider, "_git_commit", return_value="noop"
            ), patch.object(GBrainOllamaProvider, "_run", new=fake_run), patch.object(
                GBrainOllamaProvider, "_run_allow_failure", return_value=(0, "")
            ):
                provider = GBrainOllamaProvider(
                    Path(tmp),
                    embedding_model="snowflake-arctic-embed:335m",
                    embedding_dimensions=1024,
                    ollama_base_url="http://127.0.0.1:11434/v1",
                )

        self.assertIn(
            (
                "init",
                "--pglite",
                "--embedding-model",
                "ollama:snowflake-arctic-embed:335m",
                "--embedding-dimensions",
                "1024",
                "--non-interactive",
            ),
            run_calls,
        )
        self.assertNotIn(("init", "--pglite", "--no-embedding"), run_calls)
        self.assertEqual(provider.stats()["embedding_model"], "ollama:snowflake-arctic-embed:335m")
        self.assertEqual(provider.stats()["embedding_dimensions"], 1024)

    def test_environment_scrubs_hosted_embedding_credentials(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(GBrainOllamaProvider, "_git", return_value=""), patch.object(
                GBrainOllamaProvider, "_git_commit", return_value="noop"
            ), patch.object(GBrainOllamaProvider, "_run", return_value=""), patch.object(
                GBrainOllamaProvider, "_run_allow_failure", return_value=(0, "")
            ):
                provider = GBrainOllamaProvider(
                    Path(tmp),
                    embedding_model="snowflake-arctic-embed:335m",
                    embedding_dimensions=1024,
                )
        env = provider._env()
        self.assertEqual(env["OLLAMA_BASE_URL"], "http://127.0.0.1:11434/v1")
        self.assertEqual(env["GBRAIN_EMBEDDING_MODEL"], "ollama:snowflake-arctic-embed:335m")
        self.assertEqual(env["GBRAIN_EMBEDDING_DIMENSIONS"], "1024")
        for key in (
            "OPENAI_API_KEY",
            "ZEROENTROPY_API_KEY",
            "VOYAGE_API_KEY",
            "GOOGLE_GENERATIVE_AI_API_KEY",
            "OPENROUTER_API_KEY",
            "ANTHROPIC_API_KEY",
        ):
            self.assertNotIn(key, env)

    def test_existing_v1_adapter_still_contains_no_embedding_init(self):
        source = Path(GBrainProvider.__module__.replace(".", "/") + ".py")
        source = Path(__file__).resolve().parents[2] / "providers" / "gbrain" / "adapter.py"
        self.assertIn('"init", "--pglite", "--no-embedding"', source.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
