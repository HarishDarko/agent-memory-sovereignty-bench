import tempfile
import unittest
from pathlib import Path

from benchmark import manifests
from benchmark.config import load_settings
from benchmark.corpus import generate_corpus
from benchmark.events import corpus_digest


class TestManifests(unittest.TestCase):
    def test_next_run_id_increments(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            a = manifests.next_run_id(root, "2026-08-01")
            b = manifests.next_run_id(root, "2026-08-01")
            self.assertEqual(a, "2026-08-01-001")
            self.assertEqual(b, "2026-08-01-002")

    def test_prompt_digest_stable(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "prompt.md"
            p.write_text("prompt", encoding="utf-8")
            self.assertEqual(manifests.prompt_digest(p, "v1"), manifests.prompt_digest(p, "v1"))
            self.assertNotEqual(manifests.prompt_digest(p, "v1"), manifests.prompt_digest(p, "v2"))

    def test_corpus_digest_detects_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            corpus = generate_corpus(seed=3, n_persons=8, n_noise=1)
            corpus.to_files(Path(tmp))
            d1 = corpus_digest(Path(tmp) / "events.jsonl", Path(tmp) / "queries.jsonl", Path(tmp) / "ground_truth.jsonl")
            d2 = corpus_digest(Path(tmp) / "events.jsonl", Path(tmp) / "queries.jsonl", Path(tmp) / "ground_truth.jsonl")
            self.assertEqual(d1, d2)
            corpus2 = generate_corpus(seed=4, n_persons=8, n_noise=1)
            corpus2.to_files(Path(tmp))
            d3 = corpus_digest(Path(tmp) / "events.jsonl", Path(tmp) / "queries.jsonl", Path(tmp) / "ground_truth.jsonl")
            self.assertNotEqual(d1, d3)

    def test_build_manifest_required_keys(self):
        settings = load_settings()
        manifest = manifests.build_manifest(
            run_id="2026-08-01-001",
            track="controlled",
            settings=settings,
            provider_name="bm25-sqlite-fts",
            provider_version="0.1.0",
            provider_capabilities={"read_only_retrieval": True},
            control=False,
            corpus_digest_value="abcd",
            corpus_split="dev",
            prompt_digest_value="efgh",
            bench_time="2026-08-01T00:00:00Z",
            preflight={"passed": True, "results": []},
            scores={"total": 1},
            scorer_version="0.1.0",
            provider_stats={},
        )
        for key in ("run_id", "track", "benchmark_time", "reader", "memory_provider", "corpus", "runtime", "isolation", "scores"):
            self.assertIn(key, manifest)
        self.assertIsNone(manifest["reader"]["requested_model"])
        self.assertFalse(manifest["reader"]["semantic_reader_validated"])
        self.assertEqual(manifest["reader"]["mode"], "offline")


if __name__ == "__main__":
    unittest.main()
