"""Task 13: Phase 1 protocol freeze - determinism, content, and commitments."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

import scripts.freeze_protocol as freeze

REPO_ROOT = Path(__file__).resolve().parent.parent
FREEZE_PATH = REPO_ROOT / "protocols" / "v1" / "config-freeze.json"
PACKS_DIR = REPO_ROOT / "scorer_private" / "test-v1"
COMMITMENT_PATH = REPO_ROOT / "datasets" / "commitments" / "test-v1.json"


def load_freeze() -> dict:
    return json.loads(FREEZE_PATH.read_text(encoding="utf-8"))


class TestFreezeDeterminism(unittest.TestCase):
    def test_content_groups_deterministic(self):
        first = freeze.collect_groups(REPO_ROOT)
        second = freeze.collect_groups(REPO_ROOT)
        self.assertEqual(first, second)

    def test_group_digest_changes_when_file_changes(self):
        before = freeze.collect_groups(REPO_ROOT)
        # A file we know is committed and frozen; simulate a modified copy.
        prompt = REPO_ROOT / "prompts" / "reader-v1.md"
        original = prompt.read_bytes()
        try:
            prompt.write_bytes(original + b"\n# mutation probe\n")
            after = freeze.collect_groups(REPO_ROOT)
        finally:
            prompt.write_bytes(original)
        self.assertNotEqual(before["prompt"]["digest"], after["prompt"]["digest"])


class TestFreezeManifest(unittest.TestCase):
    def test_committed_freeze_matches_working_tree(self):
        errors = freeze.verify_freeze(REPO_ROOT, images={})
        # AMSB regenerated pyproject.toml and uv.lock for the new package
        # name; every other frozen content group must still match the source
        # freeze recorded in protocols/v1/config-freeze.json.
        expected_divergence = "group lock: digest mismatch; changed files: ['pyproject.toml', 'uv.lock']"
        self.assertEqual([error for error in errors if error != expected_divergence], [])
        self.assertIn(expected_divergence, errors)

    def test_reader_settings_frozen_by_pilot(self):
        freeze_json = load_freeze()
        reader = freeze_json["reader"]
        self.assertEqual(reader["model"], "deepseek-v4-flash")
        self.assertEqual(reader["expected_release"], "DeepSeek-V4-Flash-0731")
        self.assertEqual(reader["attestation_mode"], "rolling")
        self.assertFalse(reader["thinking_enabled"])
        self.assertEqual(reader["reasoning_effort"], "none")
        self.assertEqual(reader["temperature"], 0.0)
        self.assertEqual(reader["token_budget"], 2048)
        self.assertEqual(reader["repeats"], 3)
        self.assertEqual(reader["clock_start"], "2026-08-01T00:00:00Z")

    def test_prompt_hash_matches_pilot_record(self):
        freeze_json = load_freeze()
        self.assertEqual(freeze_json["prompt_file_sha256"], "5eab2ba89728e2af16293868703b9e005be6137a43b2a4f2505bb910b3e891fa")

    def test_primary_outcomes_preregistered(self):
        freeze_json = load_freeze()
        self.assertEqual(
            freeze_json["primary_outcomes"],
            [
                "complete_chain_at_5",
                "typed_answer_correctness",
                "calibrated_abstention",
                "cross_principal_leakage",
                "deletion_persistence",
                "export_round_trip_fidelity",
            ],
        )

    def test_cost_estimate_within_ceilings(self):
        freeze_json = load_freeze()
        cost = freeze_json["cost"]
        self.assertEqual(cost["requests"], 192 * 3)
        self.assertEqual(cost["repeats"], 3)
        self.assertLessEqual(cost["expected_usd"], cost["ceiling_usd_per_run"])
        self.assertLessEqual(cost["worst_case_usd"], cost["ceiling_usd_per_run"])
        self.assertLessEqual(cost["ceiling_usd_per_run"], cost["ceiling_usd_global"])
        self.assertEqual(cost["provider_native_model_calls_usd"], 0.0)

    def test_optmem_image_digest_pinned(self):
        freeze_json = load_freeze()
        optmem = freeze_json["images"]["optmem"]
        self.assertEqual(
            optmem["digest"],
            "sha256:bc64d013d37586253156302df506009c099a38592f26aefa5b9e383feb825833",
        )
        self.assertEqual(optmem["reference"], "sovbench-optmem:1fb164c")

    def test_test_commitment_verified_and_unopened(self):
        freeze_json = load_freeze()
        commitment = freeze_json["test_commitment"]
        self.assertTrue(commitment["verified"])
        self.assertTrue(commitment["packs_present"])
        self.assertEqual(len(commitment["packs"]), 3)
        for pack in commitment["packs"].values():
            self.assertEqual(pack["queries"], 64)


class TestFreezeCommitment(unittest.TestCase):
    def test_pack_commitments_verify_against_disk(self):
        if not PACKS_DIR.exists():
            self.skipTest("hidden TEST packs not present in this checkout")
        from benchmark.datasets.commitment import load_commitments, verify_pack

        commitment = load_commitments(COMMITMENT_PATH)
        errors: list[str] = []
        for pack_name, pack_commitment in sorted(commitment["packs"].items()):
            errors.extend(verify_pack(PACKS_DIR / pack_name, pack_commitment))
        self.assertEqual(errors, [])


class TestCostEstimate(unittest.TestCase):
    def test_pilot_basis_math(self):
        usage = {
            "source": "test",
            "requests": 180,
            "actual_cost_usd": 0.0258,
            "input_tokens": 97119,
            "output_tokens": 43450,
        }
        estimate = freeze.cost_estimate(usage=usage)
        self.assertEqual(estimate["requests"], 576)
        # 576 * (539.55 * 0.14 + 241.39 * 0.28) / 1e6
        self.assertAlmostEqual(estimate["expected_usd"], 0.0824, places=3)
        self.assertEqual(estimate["ceiling_usd_per_run"], 1.0)
        self.assertEqual(estimate["ceiling_usd_global"], 10.0)

    def test_pilot_usage_consistent_with_committed_result(self):
        usage = freeze.pilot_usage(REPO_ROOT)
        self.assertEqual(usage["requests"], 180)
        self.assertEqual(usage["input_tokens"] + usage["output_tokens"], 97119 + 43450)


class TestFreezeScript(unittest.TestCase):
    def test_dry_run_command_exists(self):
        self.assertTrue((REPO_ROOT / "scripts" / "run_phase0.py").exists())

    def test_pending_paths_allow_own_files(self):
        self.assertTrue(freeze._is_pending("?? protocols/", freeze.PENDING_FREEZE_PATHS))
        self.assertTrue(freeze._is_pending(" M scripts/freeze_protocol.py", freeze.PENDING_FREEZE_PATHS))
        self.assertFalse(freeze._is_pending(" M benchmark/scorer.py", freeze.PENDING_FREEZE_PATHS))

    def test_dirty_tree_outside_pending_is_refused(self):
        dirty = {
            "commit": "x" * 40,
            "describe": "x",
            "tree_clean": False,
            "uncommitted": [" M benchmark/scorer.py"],
        }
        with self.assertRaises(RuntimeError):
            freeze.build_freeze(REPO_ROOT, images={}, git=dirty)

    def test_freeze_with_only_pending_files_is_allowed(self):
        pending = {
            "commit": "x" * 40,
            "describe": "x",
            "tree_clean": False,
            "uncommitted": ["?? protocols/"],
        }
        result = freeze.build_freeze(REPO_ROOT, images={}, git=pending, require_packs=False)
        self.assertEqual(result["git"]["pending_freeze_paths"], ["protocols/"])
        self.assertEqual(result["schema"], "sovbench/protocol-freeze/1")


if __name__ == "__main__":
    unittest.main()
