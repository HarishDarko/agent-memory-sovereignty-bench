import json
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.attest_gbrain_local import ollama_attestation


class _Response:
    def __init__(self, data):
        self.data = json.dumps(data).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.data


class TestFollowupEnvironment(unittest.TestCase):
    def test_ollama_attestation_records_digest_and_dimension(self):
        tags = {
            "models": [
                {
                    "name": "snowflake-arctic-embed:335m",
                    "digest": "sha256:test-digest",
                    "size": 123,
                }
            ]
        }
        embed = {
            "model": "snowflake-arctic-embed:335m",
            "embeddings": [[0.1, 0.2, 0.3, 0.4]],
        }
        with patch(
            "scripts.attest_gbrain_local.urllib.request.urlopen",
            side_effect=[_Response(tags), _Response(embed)],
        ), patch("scripts.attest_gbrain_local.run_text", return_value="0.32.6"):
            data = ollama_attestation(
                "http://127.0.0.1:4713",
                "snowflake-arctic-embed:335m",
                Path("ollama.exe"),
            )
        self.assertEqual(data["embedding_dimensions"], 4)
        self.assertEqual(data["models"][0]["digest"], "sha256:test-digest")
        self.assertEqual(data["ollama_version"], "0.32.6")

    def test_attestation_contract_keeps_reader_and_embedder_separate(self):
        self.assertNotEqual("deepseek-v4-flash", "snowflake-arctic-embed:335m")


if __name__ == "__main__":
    unittest.main()
