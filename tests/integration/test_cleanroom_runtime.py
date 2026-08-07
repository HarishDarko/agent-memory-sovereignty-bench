"""Executable clean-room runtime probe (local images only, no downloads)."""

import os
import time
import unittest
from pathlib import Path

from benchmark.isolation.docker_probe import run_probe


REPO = Path(__file__).resolve().parent.parent.parent


@unittest.skipUnless(
    os.environ.get("SOVBENCH_RUN_DOCKER_INTEGRATION") == "1",
    "set SOVBENCH_RUN_DOCKER_INTEGRATION=1 to run the Docker clean-room integration test",
)
class TestCleanRoomRuntime(unittest.TestCase):
    def test_runtime_probe_passes_and_cleans_up(self):
        run_id = f"int-{int(time.time())}"
        evidence = run_probe(run_id=run_id, repo_root=REPO)
        self.assertTrue(evidence["passed"], evidence["errors"])
        self.assertFalse(evidence["probes"]["public_http"]["allowed"])
        self.assertFalse(evidence["probes"]["deepseek_direct"]["allowed"])
        self.assertTrue(evidence["probes"]["gateway_internal"]["reachable"])
        self.assertEqual(evidence["inspection"]["provider_containers"], 1)
        self.assertEqual(evidence["cleanup"]["containers_remaining"], 0)
        self.assertEqual(evidence["cleanup"]["networks_remaining"], 0)
        self.assertEqual(evidence["cleanup"]["volumes_remaining"], 0)


if __name__ == "__main__":
    unittest.main()
