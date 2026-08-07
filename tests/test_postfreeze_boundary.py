import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
FROZEN_PATHS = (
    REPO_ROOT / "protocols" / "v1",
    REPO_ROOT / "reports" / "protocol-v1",
    REPO_ROOT / "docs" / "reports" / "task15-native-track-research-review.md",
)


class TestPostfreezeBoundary(unittest.TestCase):
    def test_frozen_v1_artifacts_exist(self):
        for path in FROZEN_PATHS:
            self.assertTrue(path.exists(), path)

    def test_followup_root_is_separate(self):
        followup_root = REPO_ROOT / "runs" / "followups"
        self.assertNotEqual(followup_root, REPO_ROOT / "runs" / "protocol-v1")
        self.assertNotIn("protocol-v1", str(followup_root / "gbrain-native-local"))
        self.assertNotIn("protocol-v1", str(followup_root / "semantic-exit-v1"))

    def test_private_gold_is_not_under_provider_roots(self):
        if not (REPO_ROOT / "scorer_private").exists():
            self.skipTest("private gold is excluded from the OSS distribution; see docs/dataset-policy.md")
        self.assertNotIn("scorer_private", str(REPO_ROOT / "runs" / "followups"))


if __name__ == "__main__":
    unittest.main()
