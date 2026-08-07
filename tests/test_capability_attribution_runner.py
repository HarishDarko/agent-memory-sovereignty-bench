import unittest
import tempfile
from pathlib import Path
import subprocess
import sys

from benchmark.datasets.generator_v2 import generate_personal, personal_test_pack
from benchmark.clock import BenchmarkClock
from benchmark.config import Settings
from benchmark.events import GroundTruth, Query
from benchmark.model_gateway import OfflineGateway
from benchmark.providers import RetrievedItem
from benchmark.scorer import Scorer
from scripts.run_capability_attribution import SelectedQuery, execute_property, select_queries


class CapabilityAttributionRunnerTests(unittest.TestCase):
    def test_script_help_runs_from_repository_root(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [sys.executable, "-B", "scripts/run_capability_attribution.py", "--help"],
            cwd=root,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_test_selection_is_exact_and_rejects_kind_drift(self):
        corpus = personal_test_pack(1, set_name="pack-1")
        selected = select_queries(corpus.queries, split="test", pack="pack-1")
        self.assertEqual(len(selected), 20)
        self.assertEqual({row.property_name for row in selected}, {"authority", "provenance", "temporal", "scope", "deletion"})

        mutated = list(corpus.queries)
        target = next(index for index, query in enumerate(mutated) if query.query_id == "pack1_query_0050")
        mutated[target] = mutated[target].__class__(**{**mutated[target].__dict__, "kind": "historical"})
        with self.assertRaisesRegex(ValueError, "kind mismatch"):
            select_queries(mutated, split="test", pack="pack-1")

    def test_dev_selection_uses_first_two_subjects_and_governance_specials(self):
        corpus = generate_personal()
        selected = select_queries(corpus.queries, split="dev", pack="dev")
        temporal = [row for row in selected if row.property_name == "temporal"]
        self.assertEqual({row.query.subject for row in temporal}, {"person_01", "person_02"})
        self.assertTrue(any(row.query.kind == "authority_conflict" for row in selected))
        self.assertTrue(any(row.query.kind == "provenance" for row in selected))
        self.assertTrue(any(row.query.kind == "cross_user" for row in selected))

    def test_authority_execution_produces_complete_paired_grid_with_scorer_metadata(self):
        query = Query("q-auth", "Which value is correct?", "user_001", "personal", "2026-07-01T00:00:00Z", "authority_conflict", "person_01")
        items = [
            RetrievedItem("gold", "CorrectValue", 1.0, {"principal": "user_001", "scope": "personal", "available_at": "2026-06-01T00:00:00Z", "authority": "user_explicit", "source": "user", "kind": "fact"}),
            RetrievedItem("poison", "WrongValue", 0.9, {"principal": "user_001", "scope": "personal", "available_at": "2026-06-02T00:00:00Z", "authority": "external", "source": "forum_post", "kind": "poison_attempt"}),
        ]
        scorer = Scorer(gold={"q-auth": GroundTruth("q-auth", "CorrectValue", False, ("gold",))})
        with tempfile.TemporaryDirectory() as tmp:
            settings = Settings(prompt_path=Path("protocols/capability-attribution-v1/neutral-reader-v1.md"))
            neutral = OfflineGateway(settings, BenchmarkClock(query.as_of), Path(tmp) / "neutral.jsonl")
            governed_settings = Settings(prompt_path=Path("prompts/reader-v1.md"))
            governed = OfflineGateway(governed_settings, BenchmarkClock(query.as_of), Path(tmp) / "governed.jsonl")
            rows = execute_property(
                provider_name="gbrain",
                pack="dev",
                selected=SelectedQuery(query, "authority"),
                raw_items=items,
                scorer=scorer,
                gateways={"neutral": neutral, "governance": governed},
                replicates=3,
                token_budget=2048,
                deleted_event_ids=set(),
            )
        self.assertEqual(len(rows), 12)
        self.assertEqual({row["condition"] for row in rows}, {"M0P0", "M1P0", "M0P1", "M1P1"})
        self.assertEqual(len({row["reader_item_signature"] for row in rows}), 1)
        self.assertTrue(all(row["reader_correct"] for row in rows))
        self.assertTrue(all(row["forbidden_evidence_count"] == 1 for row in rows))

    def test_persistent_reader_error_stays_in_attempt_denominator(self):
        class FailingGateway:
            def generate(self, *args, **kwargs):
                raise RuntimeError("reader unavailable")

        query = Query("q-auth", "Which value is correct?", "user_001", "personal", "2026-07-01T00:00:00Z", "authority_conflict", "person_01")
        items = [RetrievedItem("gold", "CorrectValue", 1.0, {"principal": "user_001", "scope": "personal", "available_at": "2026-06-01T00:00:00Z", "authority": "user_explicit", "source": "user", "kind": "fact"})]
        scorer = Scorer(gold={"q-auth": GroundTruth("q-auth", "CorrectValue", False, ("gold",))})
        rows = execute_property(
            provider_name="gbrain",
            pack="dev",
            selected=SelectedQuery(query, "authority"),
            raw_items=items,
            scorer=scorer,
            gateways={"neutral": FailingGateway(), "governance": FailingGateway()},
            replicates=3,
            token_budget=2048,
            deleted_event_ids=set(),
        )
        self.assertEqual(len(rows), 12)
        self.assertTrue(all(row["reader_correct"] is False for row in rows))
        self.assertTrue(all("reader unavailable" in row["reader_error"] for row in rows))


if __name__ == "__main__":
    unittest.main()
