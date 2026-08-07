"""Static clean-room policy linting for the Compose definition."""

import unittest
from pathlib import Path

from benchmark.isolation.docker_policy import check_rendered_policy, check_static_policy


REPO = Path(__file__).resolve().parent.parent
BASE_COMPOSE = (REPO / "docker" / "compose.yml").read_text(encoding="utf-8")
PROBE_COMPOSE = (REPO / "docker" / "compose.probe.yml").read_text(encoding="utf-8")


class TestStaticPolicy(unittest.TestCase):
    def test_base_compose_passes_static_policy(self):
        self.assertEqual(check_static_policy(BASE_COMPOSE), [])

    def test_probe_overlay_passes_static_policy(self):
        self.assertEqual(check_static_policy(BASE_COMPOSE + "\n" + PROBE_COMPOSE), [])

    def test_rejects_host_networking(self):
        issues = check_static_policy(BASE_COMPOSE + "\n  provider:\n    network_mode: host\n")
        self.assertTrue(any("host" in issue for issue in issues))

    def test_rejects_privileged_provider(self):
        issues = check_static_policy(BASE_COMPOSE.replace("read_only: true", "privileged: true"))
        self.assertTrue(any("privileged" in issue for issue in issues))

    def test_rejects_gold_mount(self):
        text = BASE_COMPOSE + "\n  provider:\n    volumes:\n      - ./scorer_private:/gold:ro\n"
        issues = check_static_policy(text)
        self.assertTrue(any("scorer_private" in issue or "gold" in issue for issue in issues))

    def test_rejects_second_provider_state_mount(self):
        text = BASE_COMPOSE + "\n  gateway:\n    volumes:\n      - bench-data:/provider-state\n"
        issues = check_static_policy(text)
        self.assertTrue(any("provider-state" in issue and "gateway" in issue for issue in issues))

    def test_rejects_provider_without_read_only_root(self):
        text = BASE_COMPOSE.replace("    read_only: true\n", "")
        issues = check_static_policy(text)
        self.assertTrue(any("read_only" in issue for issue in issues))

    def test_rejects_missing_internal_network(self):
        text = BASE_COMPOSE.replace("  bench-internal:\n    internal: true\n", "  bench-internal:\n    driver: bridge\n")
        issues = check_static_policy(text)
        self.assertTrue(any("internal" in issue for issue in issues))

    def test_rejects_provider_on_egress_network(self):
        text = BASE_COMPOSE.replace("    networks: [bench-internal]\n", "    networks: [bench-internal, bench-egress]\n")
        issues = check_static_policy(text)
        self.assertTrue(any("bench-egress" in issue for issue in issues))


def _probe_rendered() -> dict:
    return {
        "services": {
            "gateway": {
                "image": "alpine:3.17",
                "networks": {"bench-internal": None, "bench-egress": None},
                "read_only": True,
                "security_opt": ["no-new-privileges:true"],
                "volumes": [],
            },
            "provider": {
                "image": "alpine:3.17",
                "networks": {"bench-internal": None},
                "read_only": True,
                "security_opt": ["no-new-privileges:true"],
                "cap_drop": ["ALL"],
                "mem_limit": 268435456,
                "pids_limit": 256,
                "cpus": 0.5,
                "user": "65532:65532",
                "volumes": [{"type": "volume", "source": "bench-probe-data", "target": "/provider-state"}],
            },
        },
        "networks": {
            "bench-internal": {"internal": True, "name": "sovbench-probe_bench-internal"},
            "bench-egress": {"internal": False, "name": "sovbench-probe_bench-egress"},
        },
        "volumes": {"bench-probe-data": {"name": "bench-probe-data"}},
    }


class TestRenderedPolicy(unittest.TestCase):
    def test_pinned_probe_config_passes(self):
        self.assertEqual(check_rendered_policy(_probe_rendered(), probe=True), [])

    def test_rejects_unpinned_provider_image(self):
        rendered = _probe_rendered()
        rendered["services"]["provider"]["image"] = "ghcr.io/owner/provider:latest"
        issues = check_rendered_policy(rendered, probe=True)
        self.assertTrue(any("pin" in issue for issue in issues))

    def test_rejects_provider_on_non_internal_network(self):
        rendered = _probe_rendered()
        rendered["services"]["provider"]["networks"] = {"bench-egress": None}
        issues = check_rendered_policy(rendered, probe=True)
        self.assertTrue(any("internal" in issue for issue in issues))

    def test_rejects_volume_shared_between_services(self):
        rendered = _probe_rendered()
        rendered["services"]["gateway"]["volumes"] = [
            {"type": "volume", "source": "bench-probe-data", "target": "/gateway-cache"}
        ]
        issues = check_rendered_policy(rendered, probe=True)
        self.assertTrue(any("shared" in issue for issue in issues))

    def test_rejects_missing_limits_or_capabilities(self):
        rendered = _probe_rendered()
        provider = rendered["services"]["provider"]
        provider.pop("mem_limit")
        provider["cap_drop"] = []
        issues = check_rendered_policy(rendered, probe=True)
        self.assertTrue(any("limits" in issue for issue in issues))
        self.assertTrue(any("cap" in issue for issue in issues))

    def test_probe_requires_explicit_non_root_user(self):
        rendered = _probe_rendered()
        rendered["services"]["provider"].pop("user")
        issues = check_rendered_policy(rendered, probe=True)
        self.assertTrue(any("user" in issue for issue in issues))


if __name__ == "__main__":
    unittest.main()
