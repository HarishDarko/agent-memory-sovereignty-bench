"""Run analysis: paired comparisons, failure denominators, reliability."""

import json
import tempfile
import unittest
from pathlib import Path

from benchmark import manifests
from benchmark.config import load_settings
from benchmark.events import GroundTruth, Query, write_jsonl
from benchmark.scorer import Scorer
from scripts.analyze_runs import analyze


def _build_run(run_dir: Path, provider: str, outcomes: list[tuple[str, bool]], settings, gold_path) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    gold = {
        query_id: GroundTruth(query_id, "Quill", False, ("e1",), "note")
        for query_id, _ in outcomes
    }
    write_jsonl(gold_path, [
        {
            "query_id": row.query_id,
            "answer": row.answer,
            "abstain": row.abstain,
            "gold_event_ids": list(row.gold_event_ids),
            "note": row.note,
        }
        for row in gold.values()
    ])
    scorer = Scorer(gold=gold)
    traces = []
    for query_id, correct in outcomes:
        query = Query(query_id, "What is the editor?", "user_001", "personal", "2026-08-01T00:00:00Z")
        score = scorer.score_query(
            query,
            __import__("benchmark.providers", fromlist=["RetrievalResult"]).RetrievalResult(items=[]),
            __import__("benchmark.model_gateway", fromlist=["ModelResponse"]).ModelResponse(
                structured={"answer": "Quill" if correct else "Wrong", "confidence": 1.0, "abstain": False, "evidence_ids": ["e1"]},
                model_id="test",
                mode="offline",
                prompt_hash="h" * 64,
                request_tokens=1,
                response_tokens=1,
            ),
        )
        traces.append(
            {
                "query_id": query_id,
                "question": query.question,
                "principal": query.principal,
                "subject": "person_01",
                "as_of": query.as_of,
                "kind": query.kind,
                "checkpoint": {"as_of": query.as_of, "eligible_event_ids": [], "lifecycle_actions": [], "state_hash": "x"},
                "retrieval": {"item_ids": [], "scores": [], "raw": {}},
                "evidence": {"tokens": 1, "item_ids": []},
                "reader": {
                    "mode": "offline",
                    "model_id": "test",
                    "structured": {"answer": "Quill" if correct else "Wrong", "abstain": False, "evidence_ids": ["e1"]},
                    "retries": 0,
                },
                "score": score.to_dict(),
            }
        )
    manifest = manifests.build_manifest(
        run_id=run_dir.name,
        track="controlled",
        settings=settings,
        provider_name=provider,
        provider_version="0.1.0",
        provider_capabilities={"read_only_retrieval": True},
        control=False,
        corpus_digest_value="abcd",
        corpus_split="dev",
        prompt_digest_value="e" * 64,
        bench_time="2026-08-01T00:00:00Z",
        preflight={"passed": True, "results": []},
        scores={"reader_accuracy": 1.0, "total": len(outcomes)},
        scorer_version="0.1.0",
        provider_stats={},
        status="completed_publishable",
        reader={
            "provider": "DeepSeek API",
            "requested_model": "deepseek-v4-flash",
            "expected_release": "DeepSeek-V4-Flash-0731",
            "actual_model": "deepseek-v4-flash-0731",
            "semantic_reader_validated": True,
        },
        publication={"eligible": True, "reasons": []},
        dataset_validation={"passed": True, "errors": [], "warnings": []},
    )
    manifests.write_manifest(run_dir, manifest)
    manifests.write_traces(run_dir, traces)
    manifests.write_scores(run_dir, {"reader_accuracy": 1.0, "total": len(outcomes)})


class TestAnalyzeRuns(unittest.TestCase):
    def test_analysis_reports_comparisons_failures_and_reliability(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = load_settings()
            settings.prompt_path = root / "prompts" / "reader-v1.md"
            settings.prompt_path.parent.mkdir(parents=True, exist_ok=True)
            settings.prompt_path.write_text("prompt", encoding="utf-8")
            outcomes_a = [("q1", True), ("q2", True), ("q3", False), ("q4", True)]
            outcomes_b = [("q1", False), ("q2", True), ("q3", True), ("q4", True)]
            run_a = root / "run-a"
            run_b = root / "run-b"
            _build_run(run_a, "provider-a", outcomes_a, settings, root / "gold-a.jsonl")
            _build_run(run_b, "provider-b", outcomes_b, settings, root / "gold-b.jsonl")
            invalid = root / "run-invalid"
            invalid.mkdir(parents=True, exist_ok=True)
            invalid_manifest = manifests.build_manifest(
                run_id="run-invalid",
                track="controlled",
                settings=settings,
                provider_name="provider-c",
                provider_version="0.1.0",
                provider_capabilities={},
                control=False,
                corpus_digest_value="x",
                corpus_split="dev",
                prompt_digest_value="e" * 64,
                bench_time="2026-08-01T00:00:00Z",
                preflight={"passed": False, "results": []},
                scores=None,
                scorer_version="0.1.0",
                provider_stats={},
                status="aborted_preflight",
                status_reason="probe failed",
                publication={"eligible": False, "reasons": ["preflight"]},
                dataset_validation={"passed": True, "errors": [], "warnings": []},
            )
            manifests.write_manifest(invalid, invalid_manifest)

            report = analyze(run_dirs=[run_a, run_b, invalid], seed=20260805, resamples=200)
            self.assertEqual(report["runs"]["run-a"]["attempts"], 4)
            self.assertEqual(report["runs"]["run-invalid"]["status"], "aborted_preflight")
            self.assertEqual(report["failures"]["invalid_runs"], ["run-invalid"])
            comparison = report["comparisons"]["reader_accuracy"][0]
            self.assertEqual(comparison["a"], "run-a")
            self.assertEqual(comparison["b"], "run-b")
            self.assertIn("bootstrap", comparison)
            self.assertIn("mcnemar", comparison)
            self.assertIn("pass_at_1", report["runs"]["run-a"])
            self.assertTrue(json.dumps(report))


if __name__ == "__main__":
    unittest.main()
