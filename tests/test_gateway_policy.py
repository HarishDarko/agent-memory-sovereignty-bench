"""Policy gate for the model gateway proxy."""

import unittest
from pathlib import Path

from benchmark.gateway.policy import BudgetExceeded, BudgetState, GatewayPolicy, attest_model, check_request, check_response, check_upstream_target


def _policy(**overrides) -> GatewayPolicy:
    values = dict(
        allowed_upstream_hosts=["api.deepseek.com"],
        allowed_upstream_paths=["/chat/completions", "/v1/chat/completions"],
        allowed_model_aliases=["deepseek-v4-flash"],
        max_messages=2,
        max_retries=2,
        max_requests_per_run=1000,
        max_tokens_per_run=2_000_000,
        max_cost_usd_per_run=1.0,
        max_requests_global=10000,
        max_tokens_global=20_000_000,
        max_cost_usd_global=10.0,
        price_per_million_input=0.0,
        price_per_million_output=0.0,
        attestation_mode="rolling",
        expected_release="DeepSeek-V4-Flash-0731",
    )
    values.update(overrides)
    return GatewayPolicy(**values)


def _request(model="deepseek-v4-flash"):
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": "reader"},
            {"role": "user", "content": "question + evidence"},
        ],
        "temperature": 0.0,
        "stream": False,
    }


class TestUpstreamTarget(unittest.TestCase):
    def test_official_target_passes(self):
        policy = _policy()
        self.assertEqual(check_upstream_target(policy, "https://api.deepseek.com/chat/completions"), [])
        self.assertEqual(check_upstream_target(policy, "https://api.deepseek.com/v1/chat/completions"), [])

    def test_non_allowlisted_host_and_path_rejected(self):
        policy = _policy()
        self.assertTrue(any("host" in i for i in check_upstream_target(policy, "https://evil.example.com/chat/completions")))
        self.assertTrue(any("path" in i for i in check_upstream_target(policy, "https://api.deepseek.com/v1/models")))
        self.assertTrue(any("scheme" in i for i in check_upstream_target(policy, "http://api.deepseek.com/chat/completions")))

    def test_policy_loads_from_config_file(self):
        policy = GatewayPolicy.load(Path(__file__).resolve().parent.parent / "config" / "gateway-policy.toml")
        self.assertEqual(policy.allowed_upstream_hosts, ["api.deepseek.com"])
        self.assertEqual(policy.allowed_model_aliases, ["deepseek-v4-flash"])
        self.assertEqual(policy.attestation_mode, "rolling")


class TestRequestPolicy(unittest.TestCase):
    def test_valid_identity_and_messages_pass(self):
        issues = check_request(_policy(), _request(), {"run_id": "r-1", "provider_id": "p-1"})
        self.assertEqual(issues, [])

    def test_missing_identity_rejected(self):
        issues = check_request(_policy(), _request(), {})
        self.assertTrue(any("run_id" in i for i in issues))
        self.assertTrue(any("provider_id" in i for i in issues))

    def test_conversation_history_reuse_rejected(self):
        request = _request()
        request["messages"].append({"role": "assistant", "content": "previous turn"})
        request["messages"].append({"role": "user", "content": "next turn"})
        issues = check_request(_policy(), request, {"run_id": "r-1", "provider_id": "p-1"})
        self.assertTrue(any("history" in i.lower() for i in issues))

    def test_unknown_model_alias_rejected(self):
        issues = check_request(_policy(), _request(model="gpt-4o"), {"run_id": "r-1", "provider_id": "p-1"})
        self.assertTrue(any("model" in i for i in issues))


class TestBudget(unittest.TestCase):
    def test_per_run_request_ceiling_fails_closed(self):
        policy = _policy(max_requests_per_run=1)
        state = BudgetState()
        state.check_and_charge(policy, "r-1", input_tokens=10, output_tokens=10)
        with self.assertRaises(BudgetExceeded):
            state.check_and_charge(policy, "r-1", input_tokens=10, output_tokens=10)

    def test_token_ceiling_fails_closed_before_dispatch(self):
        policy = _policy(max_tokens_per_run=50)
        state = BudgetState()
        with self.assertRaises(BudgetExceeded):
            state.check_and_charge(policy, "r-1", input_tokens=60, output_tokens=0)

    def test_global_ceiling_fails_closed(self):
        policy = _policy(max_requests_global=2)
        state = BudgetState()
        state.check_and_charge(policy, "r-1", 1, 1)
        state.check_and_charge(policy, "r-2", 1, 1)
        with self.assertRaises(BudgetExceeded):
            state.check_and_charge(policy, "r-3", 1, 1)

    def test_cost_ceiling_fails_closed(self):
        policy = _policy(
            price_per_million_input=1_000_000.0,
            price_per_million_output=1_000_000.0,
            max_cost_usd_per_run=0.5,
        )
        state = BudgetState()
        with self.assertRaises(BudgetExceeded):
            state.check_and_charge(policy, "r-1", input_tokens=1000, output_tokens=1000)

    def test_advisory_budget_records_without_refusing(self):
        policy = _policy(
            price_per_million_input=1_000_000.0,
            price_per_million_output=1_000_000.0,
            max_cost_usd_per_run=0.0,
            enforce_budget=False,
        )
        state = BudgetState()
        state.check_and_charge(policy, "r-1", input_tokens=1000, output_tokens=1000)
        self.assertEqual(state.run_cost["r-1"], 2000.0)
        self.assertEqual(state.global_requests, 1)
        # and a second call past every ceiling still records, never refuses
        state.check_and_charge(policy, "r-1", input_tokens=1000, output_tokens=1000)
        self.assertEqual(state.run_requests["r-1"], 2)


class TestResponsePolicy(unittest.TestCase):
    def test_complete_response_passes(self):
        payload = {
            "id": "req-1",
            "model": "deepseek-v4-flash-0731",
            "choices": [{"message": {"content": "{}"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 3},
        }
        self.assertEqual(check_response(_policy(), payload), [])

    def test_missing_identity_or_usage_rejected(self):
        policy = _policy()
        self.assertTrue(any("id" in i for i in check_response(policy, {"model": "m", "choices": []})))
        self.assertTrue(any("model" in i for i in check_response(policy, {"id": "x", "choices": []})))
        self.assertTrue(any("choices" in i for i in check_response(policy, {"id": "x", "model": "m"})))
        self.assertTrue(
            any("usage" in i for i in check_response(policy, {"id": "x", "model": "m", "choices": [{}]}))
        )


class TestAttestation(unittest.TestCase):
    def test_rolling_mode_labels_alias_without_matching_evidence(self):
        result = attest_model(
            requested="deepseek-v4-flash",
            returned="deepseek-v4-flash",
            expected_release="DeepSeek-V4-Flash-0731",
            mode="rolling",
        )
        self.assertTrue(result["ok"])
        self.assertIn("rolling", result["label"].lower())
        self.assertNotIn("0731", result["label"])

    def test_strict_mode_requires_release_evidence(self):
        policy = _policy(attestation_mode="strict")
        result = attest_model(
            requested="deepseek-v4-flash",
            returned="deepseek-v4-flash",
            expected_release=policy.expected_release,
            mode="strict",
        )
        self.assertFalse(result["ok"])
        result_ok = attest_model(
            requested="deepseek-v4-flash",
            returned="deepseek-v4-flash-0731",
            expected_release=policy.expected_release,
            mode="strict",
        )
        self.assertTrue(result_ok["ok"])


if __name__ == "__main__":
    unittest.main()
