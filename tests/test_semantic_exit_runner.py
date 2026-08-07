import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from benchmark.events import load_events
from scripts import run_semantic_memory_exit as exit_run


class SemanticExitRunnerTests(unittest.TestCase):
    def test_fidelity_is_explicit_per_property_and_does_not_use_composite_score(self):
        if not exit_run.GOLD_PATH.exists():
            self.skipTest("private semantic-exit gold is excluded from the OSS distribution")
        events = load_events(exit_run.DATASET / "events.jsonl")
        gold = json.loads(exit_run.GOLD_PATH.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            artifact = Path(tmp)
            (artifact / "export.md").write_text("event_id: exit_event_001\nsource: user\n\nMy emergency contact is Rowan Lee.\n", encoding="utf-8")
            matrix = exit_run._fidelity_matrix(events[:1], gold, artifact)
        self.assertIn("per_event", matrix)
        self.assertIn("summary", matrix)
        self.assertIn("factual_content", matrix["per_event"]["exit_event_001"])
        self.assertNotIn("composite_score", matrix)

    def test_provider_roots_are_distinct_and_gold_is_not_under_them(self):
        self.assertEqual(len(set(exit_run.PROVIDERS)), 3)
        self.assertNotIn("scorer_private", str(exit_run.RUN_ROOT / "gbrain"))
        self.assertNotIn("scorer_private", str(exit_run.RUN_ROOT / "mem0"))
        self.assertNotIn("scorer_private", str(exit_run.RUN_ROOT / "hindsight"))

    def test_destructive_receipt_is_fail_closed_to_exact_run_root(self):
        class Provider:
            def cleanup(self):
                pass

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "provider"
            (root / "nested").mkdir(parents=True)
            (root / "nested" / "state.txt").write_text("state", encoding="utf-8")
            receipt = exit_run._destructive_receipt("test", Provider(), root, None)
            self.assertTrue(receipt["destroyed"])
            self.assertFalse(root.exists())
