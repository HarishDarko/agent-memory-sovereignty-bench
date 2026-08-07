"""OptMem adapter: retrieval mapping, append-only semantics, contract."""

import os
import tempfile
import unittest
from pathlib import Path

from benchmark.events import Event, Query
from benchmark.providers import CapabilityNotSupported
from providers.compliance import ProviderMeta, run_contract
from providers.optmem.adapter import OptMemProvider


REPO = Path(__file__).resolve().parent.parent.parent
MEMO_PATH = Path(os.environ.get("SOVBENCH_OPTMEM_MEMO", REPO / ".optmem" / "memo"))


def _events():
    return [
        Event("ev-current", "2026-05-01T00:00:00Z", "user_001", "personal", "user_explicit", "user",
              "person_01's preferred editor is Quill.", subject="person_01"),
        Event("ev-future", "2099-01-01T00:00:00Z", "user_001", "personal", "user_explicit", "user",
              "person_01's future secret is FUTURE-77.", subject="person_01"),
        Event("ev-other", "2026-05-02T00:00:00Z", "user_002", "personal", "user_explicit", "user",
              "person_02's private keycode is Cipher-77.", subject="person_02"),
    ]


def _query(as_of="2026-07-01T00:00:00Z", principal="user_001", question="What is person_01's preferred editor?"):
    return Query("q1", question, principal, "personal", as_of)


class TestOptMemAdapter(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.provider = OptMemProvider(Path(self.tmp.name), memo_path=MEMO_PATH)
        self.provider.ingest(_events())

    def tearDown(self):
        self.tmp.cleanup()

    def test_retrieves_relevant_memories(self):
        ids = {item.item_id for item in self.provider.retrieve(_query()).items}
        self.assertIn("ev-current", ids)
        self.assertNotIn("ev-other", ids)

    def test_future_events_excluded_by_adapter_as_of(self):
        ids = {item.item_id for item in self.provider.retrieve(_query()).items}
        self.assertNotIn("ev-future", ids)

    def test_principal_scoping(self):
        ids = {item.item_id for item in self.provider.retrieve(
            _query(principal="user_002", question="What is person_02's private keycode?")
        ).items}
        self.assertEqual(ids, {"ev-other"})

    def test_delete_is_unsupported_by_design(self):
        with self.assertRaises(CapabilityNotSupported):
            self.provider.delete("ev-current")

    def test_dedup(self):
        result = self.provider.ingest(_events()[:1])
        self.assertEqual(result.ingested, 0)

    def test_snapshot_restore_roundtrip(self):
        snapshot = self.provider.snapshot()
        self.provider.restore(snapshot)
        ids = {item.item_id for item in self.provider.retrieve(_query()).items}
        self.assertIn("ev-current", ids)

    def test_export_import_roundtrip(self):
        exported = self.provider.export()
        self.provider.reset()
        self.provider.import_data(exported)
        ids = {item.item_id for item in self.provider.retrieve(_query()).items}
        self.assertIn("ev-current", ids)


class TestOptMemContract(unittest.TestCase):
    def test_contract_passes_with_delete_unsupported(self):
        meta = ProviderMeta(
            name="optmem",
            adapter_version="0.1.0",
            upstream_version="1fb164c",
            upstream_commit="1fb164cf39028047781f72ac3bb1e5a691c1dcb0",
            image_digest="n/a-local",
            config_hash="c" * 64,
            license="no-license-file (all rights reserved by default)",
            telemetry="none",
            external_dependencies=[],
            network_needs=[],
        )
        with tempfile.TemporaryDirectory() as tmp:
            report = run_contract(meta, lambda data_dir: OptMemProvider(data_dir, memo_path=MEMO_PATH), Path(tmp))
        self.assertTrue(report["passed"], report["checks"])
        self.assertEqual(report["checks"]["canary_deleted"]["outcome"], "not_applicable")
        self.assertEqual(report["checks"]["error_normalization"]["outcome"], "not_applicable")
        self.assertEqual(report["checks"]["export_import"]["outcome"], "native")
        self.assertEqual(report["checks"]["restart"]["outcome"], "native")


if __name__ == "__main__":
    unittest.main()
