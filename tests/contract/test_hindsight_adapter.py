"""Hindsight adapter contract tests (gated on a running pinned API)."""

import os
import tempfile
import unittest
from pathlib import Path

from benchmark.events import Event, Query
from providers.compliance import ProviderMeta, run_contract
from providers.hindsight.adapter import HindsightProvider


def _available() -> bool:
    if os.environ.get("SOVBENCH_RUN_HINDSIGHT") != "1":
        return False
    return bool(os.environ.get("HINDSIGHT_API_URL"))


def _events():
    return [
        Event("hs-current", "2026-05-01T00:00:00Z", "user_001", "personal", "user_explicit", "user",
              "person_01's preferred editor is Quill.", subject="person_01"),
        Event("hs-future", "2099-01-01T00:00:00Z", "user_001", "personal", "user_explicit", "user",
              "person_01's future secret is FUTURE-77.", subject="person_01"),
        Event("hs-other", "2026-05-02T00:00:00Z", "user_002", "personal", "user_explicit", "user",
              "person_02's private keycode is Cipher-77.", subject="person_02"),
    ]


def _query(as_of="2026-07-01T00:00:00Z", principal="user_001", question="What is person_01's preferred editor?"):
    return Query("q1", question, principal, "personal", as_of)


@unittest.skipUnless(_available(), "set SOVBENCH_RUN_HINDSIGHT=1 and HINDSIGHT_API_URL")
class TestHindsightAdapter(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.provider = HindsightProvider(Path(self.tmp.name))
        self.provider.ingest(_events())

    def tearDown(self):
        try:
            self.provider.cleanup()
        except Exception:
            pass
        self.tmp.cleanup()

    def test_retrieves_relevant_memories(self):
        ids = {item.item_id for item in self.provider.retrieve(_query()).items}
        self.assertIn("hs-current", ids)

    def test_future_events_excluded_by_adapter_as_of(self):
        ids = {item.item_id for item in self.provider.retrieve(_query()).items}
        self.assertNotIn("hs-future", ids)

    def test_principal_scoping(self):
        ids = {item.item_id for item in self.provider.retrieve(
            _query(principal="user_002", question="What is person_02's private keycode?")
        ).items}
        self.assertEqual(ids, {"hs-other"})

    def test_delete_removes_memory(self):
        self.assertTrue(self.provider.delete("hs-current"))
        ids = {item.item_id for item in self.provider.retrieve(_query()).items}
        self.assertNotIn("hs-current", ids)

    def test_export_import_roundtrip(self):
        exported = self.provider.export()
        self.provider.reset()
        self.provider.import_data(exported)
        ids = {item.item_id for item in self.provider.retrieve(_query()).items}
        self.assertIn("hs-current", ids)


@unittest.skipUnless(_available(), "set SOVBENCH_RUN_HINDSIGHT=1 and HINDSIGHT_API_URL")
class TestHindsightContract(unittest.TestCase):
    def test_contract_passes(self):
        meta = ProviderMeta(
            name="hindsight",
            adapter_version="0.1.0",
            upstream_version="0.8.6",
            upstream_commit="797faf7981ce9332e2ce7c922471b72b506b4065",
            image_digest="n/a-local",
            config_hash="h" * 64,
            license="MIT",
            telemetry="none",
            external_dependencies=["hindsight-api", "postgres+pgvector"],
            network_needs=[],
        )
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            report = run_contract(meta, lambda data_dir: HindsightProvider(data_dir), Path(tmp))
        self.assertTrue(report["passed"], report["checks"])


if __name__ == "__main__":
    unittest.main()
