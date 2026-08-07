"""Cost-gated reader-protocol pilot harness."""

import unittest
from pathlib import Path
from types import SimpleNamespace

from benchmark.config import Settings, load_settings
from benchmark.reader_validation import (
    EXPECTED_CASE_COUNTS,
    PilotGateError,
    check_live_gate,
    estimate_cost,
    live_settings,
    load_cases,
    load_configs,
    run_pilot,
    select_best,
    validate_cases,
)


REPO = Path(__file__).resolve().parent.parent
PILOT = REPO / "experiments" / "reader-pilot"


class TestPilotFixtures(unittest.TestCase):
    def test_cases_file_matches_the_preregistered_design(self):
        cases = load_cases(PILOT / "cases.jsonl")
        self.assertEqual(len(cases), 20)
        counts = {}
        for case in cases:
            counts[case.kind] = counts.get(case.kind, 0) + 1
        self.assertEqual(counts, EXPECTED_CASE_COUNTS)
        validate_cases(cases)

    def test_configs_file_has_preregistered_variants(self):
        configs = load_configs(PILOT / "configs.toml")
        self.assertEqual(len(configs), 3)
        names = {config["name"] for config in configs}
        self.assertIn("thinking-high-temp0", names)
        for config in configs:
            self.assertIn(config["thinking_enabled"], (True, False))
            self.assertIn("temperature", config)


class TestDryRun(unittest.TestCase):
    def test_offline_dry_run_produces_complete_aggregates(self):
        cases = load_cases(PILOT / "cases.jsonl")
        configs = load_configs(PILOT / "configs.toml")
        result = run_pilot(
            cases=cases,
            configs=configs,
            gateway_factory=lambda settings: OfflineStub(settings),
            repeats=2,
            budget=2048,
        )
        self.assertEqual(result["mode"], "dry-run")
        self.assertEqual(len(result["configs"]), 3)
        for aggregate in result["configs"]:
            self.assertEqual(aggregate["json_valid"], 1.0)
            self.assertEqual(aggregate["oracle_correct"], 1.0)
            self.assertEqual(aggregate["abstain_correct"], 1.0)
            self.assertEqual(aggregate["evidence_id_valid"], 1.0)
        self.assertIn("selection", result)

    def test_selection_hierarchy_prefers_json_validity(self):
        aggregates = [
            {"name": "high-oracle", "json_valid": 0.5, "oracle_correct": 1.0, "abstain_correct": 1.0, "evidence_id_valid": 1.0, "mean_tokens": 100},
            {"name": "high-json", "json_valid": 1.0, "oracle_correct": 0.8, "abstain_correct": 1.0, "evidence_id_valid": 1.0, "mean_tokens": 120},
        ]
        selected, reason = select_best(aggregates)
        self.assertEqual(selected, "high-json")
        self.assertIn("json", reason)

    def test_selection_tie_breaks_on_tokens(self):
        aggregates = [
            {"name": "a", "json_valid": 1.0, "oracle_correct": 1.0, "abstain_correct": 1.0, "evidence_id_valid": 1.0, "mean_tokens": 200},
            {"name": "b", "json_valid": 1.0, "oracle_correct": 1.0, "abstain_correct": 1.0, "evidence_id_valid": 1.0, "mean_tokens": 90},
        ]
        selected, _ = select_best(aggregates)
        self.assertEqual(selected, "b")


class TestNondeterminism(unittest.TestCase):
    def test_divergent_repeats_flag_material_nondeterminism(self):
        cases = load_cases(PILOT / "cases.jsonl")
        configs = load_configs(PILOT / "configs.toml")

        class FlipStub:
            mode = "offline"

            def __init__(self, settings):
                self.settings = settings
                self.calls = 0

            def describe(self):
                return {"semantic_reader_validated": False}

            def generate(self, query, evidence, prompt_version):
                self.calls += 1
                flip = self.calls % 2 == 0
                return SimpleNamespace(
                    structured={
                        "answer": None if flip else (evidence[0].text if evidence else None),
                        "abstain": flip,
                        "evidence_ids": [],
                    },
                    request_tokens=1,
                    response_tokens=1,
                )

        result = run_pilot(
            cases=cases,
            configs=configs,
            gateway_factory=lambda settings: FlipStub(settings),
            repeats=2,
            budget=2048,
        )
        self.assertTrue(result["nondeterminism"]["detected"])
        self.assertEqual(result["nondeterminism"]["recommended_repeats"], 5)


class TestCostGate(unittest.TestCase):
    def test_live_gate_requires_key_and_approval(self):
        settings = load_settings()
        settings.api_key = ""
        with self.assertRaises(PilotGateError):
            check_live_gate(settings, approved_env={})
        settings.api_key = "sk-test"
        with self.assertRaises(PilotGateError):
            check_live_gate(settings, approved_env={})
        check_live_gate(settings, approved_env={"SOVBENCH_PILOT_COST_APPROVED": "1"})

    def test_live_settings_route_through_proxy_with_identity(self):
        settings = live_settings(
            base=load_settings(),
            proxy_url="http://127.0.0.1:8000",
            config={"thinking_enabled": True, "reasoning_effort": "high", "temperature": 0.0},
        )
        self.assertEqual(settings.gateway_url, "http://127.0.0.1:8000")
        self.assertTrue(settings.identity_run_id.startswith("reader-pilot-"))
        self.assertEqual(settings.identity_provider_id, "reader-pilot")
        self.assertTrue(settings.thinking_enabled)
        self.assertEqual(settings.gateway_mode, "deepseek")

    def test_cost_estimate_math(self):
        cases = load_cases(PILOT / "cases.jsonl")
        configs = load_configs(PILOT / "configs.toml")
        estimate = estimate_cost(
            cases=cases,
            configs=configs,
            repeats=3,
            price_per_million_input=0.14,
            price_per_million_output=0.28,
            thinking_output_tokens=8000,
            plain_output_tokens=400,
            system_prompt="reader prompt",
        )
        self.assertGreater(estimate["requests"], 0)
        self.assertEqual(estimate["requests"], 20 * 3 * 3)
        self.assertGreater(estimate["max_cost_usd"], 0.0)
        self.assertLess(estimate["max_cost_usd"], 1.0)

class OfflineStub:
    """Minimal deterministic stub mirroring the offline gateway semantics."""

    mode = "offline"

    def __init__(self, settings):
        self.settings = settings

    def describe(self):
        return {"semantic_reader_validated": False}

    def generate(self, query, evidence, prompt_version):
        if not evidence:
            structured = {"answer": None, "confidence": 1.0, "abstain": True, "evidence_ids": []}
        else:
            structured = {
                "answer": evidence[0].text,
                "confidence": 1.0,
                "abstain": False,
                "evidence_ids": [evidence[0].item_id],
            }
        return SimpleNamespace(
            structured=structured,
            request_tokens=10,
            response_tokens=5,
            latency_ms=0.1,
        )


if __name__ == "__main__":
    unittest.main()
