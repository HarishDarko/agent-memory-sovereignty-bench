"""GBrain adapter contract tests (gated on the pinned CLI being installed)."""

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from benchmark.events import Event, Query
from providers.compliance import ProviderMeta, run_contract
from providers.gbrain.adapter import GBrainProvider


REPO = Path(__file__).resolve().parent.parent.parent
GBRAIN_BIN = os.environ.get("GBRAIN_BIN", "gbrain")


def _available() -> bool:
    if os.environ.get("SOVBENCH_RUN_GBRAIN") != "1":
        return False
    return shutil.which(GBRAIN_BIN) is not None


def _events():
    return [
        Event("gb-current", "2026-05-01T00:00:00Z", "user_001", "personal", "user_explicit", "user",
              "person_01's preferred editor is Quill.", subject="person_01"),
        Event("gb-future", "2099-01-01T00:00:00Z", "user_001", "personal", "user_explicit", "user",
              "person_01's future secret is FUTURE-77.", subject="person_01"),
        Event("gb-other", "2026-05-02T00:00:00Z", "user_002", "personal", "user_explicit", "user",
              "person_02's private keycode is Cipher-77.", subject="person_02"),
    ]


def _query(as_of="2026-07-01T00:00:00Z", principal="user_001", question="What is person_01's preferred editor?"):
    return Query("q1", question, principal, "personal", as_of)


@unittest.skipUnless(_available(), "set SOVBENCH_RUN_GBRAIN=1 and install the pinned gbrain CLI")
class TestGBrainAdapter(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.provider = GBrainProvider(Path(self.tmp.name), gbrain_bin=GBRAIN_BIN, timeout_s=600.0)
        self.provider.ingest(_events())

    def tearDown(self):
        try:
            self.provider.cleanup()
        except Exception:
            pass
        self._retry_rmtree(Path(self.tmp.name))
        self.tmp.cleanup()

    def _retry_rmtree(self, path: Path, tries: int = 8):
        import shutil
        import time

        for attempt in range(tries):
            try:
                shutil.rmtree(path)
                return
            except PermissionError:
                if attempt == tries - 1:
                    return  # host lock; temp cleanup is best-effort in tests
                time.sleep(0.75 * (attempt + 1))

    def test_retrieves_relevant_pages(self):
        ids = {item.item_id for item in self.provider.retrieve(_query()).items}
        self.assertIn("gb-current", ids)
        self.assertNotIn("gb-other", ids)

    def test_future_events_excluded_by_adapter_as_of(self):
        ids = {item.item_id for item in self.provider.retrieve(_query()).items}
        self.assertNotIn("gb-future", ids)

    def test_delete_removes_page(self):
        self.assertTrue(self.provider.delete("gb-current"))
        ids = {item.item_id for item in self.provider.retrieve(_query()).items}
        self.assertNotIn("gb-current", ids)

    def test_snapshot_restore_roundtrip(self):
        snapshot = self.provider.snapshot()
        self.provider.restore(snapshot)
        ids = {item.item_id for item in self.provider.retrieve(_query()).items}
        self.assertIn("gb-current", ids)

    def test_export_import_roundtrip(self):
        exported = self.provider.export()
        self.provider.reset()
        self.provider.import_data(exported)
        ids = {item.item_id for item in self.provider.retrieve(_query()).items}
        self.assertIn("gb-current", ids)


@unittest.skipUnless(_available(), "set SOVBENCH_RUN_GBRAIN=1 and install the pinned gbrain CLI")
class TestGBrainContract(unittest.TestCase):
    def test_contract_passes(self):
        meta = ProviderMeta(
            name="gbrain",
            adapter_version="0.1.0",
            upstream_version="0.42.73.2",
            upstream_commit="15b9863d13635d173562a54f55a1d388bfcf546b",
            image_digest="n/a-local",
            config_hash="g" * 64,
            license="MIT",
            telemetry="none",
            external_dependencies=["bun", "gbrain"],
            network_needs=[],
        )
        with tempfile.TemporaryDirectory() as tmp:
            report = run_contract(meta, lambda data_dir: GBrainProvider(data_dir, gbrain_bin=GBRAIN_BIN, timeout_s=600.0), Path(tmp))
        self.assertTrue(report["passed"], report["checks"])


if __name__ == "__main__":
    unittest.main()
