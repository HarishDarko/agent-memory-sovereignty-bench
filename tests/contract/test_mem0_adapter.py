"""Mem0 OSS adapter contract tests (gated on the pinned package being installed)."""

import os
import tempfile
import unittest
from pathlib import Path

from benchmark.events import Event, Query
from providers.compliance import ProviderMeta, run_contract
from providers.mem0.adapter import Mem0Provider


def _available() -> bool:
    if os.environ.get("SOVBENCH_RUN_MEM0") != "1":
        return False
    try:
        import mem0  # noqa: F401

        return True
    except ImportError:
        return False


def _events():
    return [
        Event("m0-current", "2026-05-01T00:00:00Z", "user_001", "personal", "user_explicit", "user",
              "person_01's preferred editor is Quill.", subject="person_01"),
        Event("m0-future", "2099-01-01T00:00:00Z", "user_001", "personal", "user_explicit", "user",
              "person_01's future secret is FUTURE-77.", subject="person_01"),
        Event("m0-other", "2026-05-02T00:00:00Z", "user_002", "personal", "user_explicit", "user",
              "person_02's private keycode is Cipher-77.", subject="person_02"),
    ]


def _query(as_of="2026-07-01T00:00:00Z", principal="user_001", question="What is person_01's preferred editor?"):
    return Query("q1", question, principal, "personal", as_of)


@unittest.skipUnless(_available(), "set SOVBENCH_RUN_MEM0=1 and install the pinned mem0ai package")
class TestMem0Adapter(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.provider = Mem0Provider(Path(self.tmp.name))
        self.provider.ingest(_events())

    def tearDown(self):
        try:
            self.provider.cleanup()
        except Exception:
            pass
        self.tmp.cleanup()

    def test_telemetry_is_disabled(self):
        env = self.provider._env()
        self.assertEqual(env["MEM0_TELEMETRY"], "false")
        import mem0.memory.telemetry as telemetry

        self.assertIs(telemetry.MEM0_TELEMETRY, False)

    def test_retrieves_relevant_memories(self):
        ids = {item.item_id for item in self.provider.retrieve(_query()).items}
        self.assertIn("m0-current", ids)

    def test_future_events_excluded_by_adapter_as_of(self):
        ids = {item.item_id for item in self.provider.retrieve(_query()).items}
        self.assertNotIn("m0-future", ids)

    def test_principal_scoping(self):
        ids = {item.item_id for item in self.provider.retrieve(
            _query(principal="user_002", question="What is person_02's private keycode?")
        ).items}
        self.assertEqual(ids, {"m0-other"})

    def test_delete_removes_memory(self):
        self.assertTrue(self.provider.delete("m0-current"))
        ids = {item.item_id for item in self.provider.retrieve(_query()).items}
        self.assertNotIn("m0-current", ids)

    def test_restart_preserves_state(self):
        self.provider.restart()
        ids = {item.item_id for item in self.provider.retrieve(_query()).items}
        self.assertIn("m0-current", ids)

    def test_export_import_roundtrip(self):
        exported = self.provider.export()
        self.provider.reset()
        self.provider.import_data(exported)
        ids = {item.item_id for item in self.provider.retrieve(_query()).items}
        self.assertIn("m0-current", ids)


@unittest.skipUnless(_available(), "set SOVBENCH_RUN_MEM0=1 and install the pinned mem0ai package")
class TestMem0Contract(unittest.TestCase):
    def test_contract_passes(self):
        meta = ProviderMeta(
            name="mem0",
            adapter_version="0.1.0",
            upstream_version="2.0.17",
            upstream_commit="3f39fba28f7781aaf581f64a4af39d017af65835",
            image_digest="n/a-local",
            config_hash="m" * 64,
            license="Apache-2.0",
            telemetry="disabled",
            external_dependencies=["mem0ai", "chromadb", "fastembed"],
            network_needs=[],
        )
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            report = run_contract(meta, lambda data_dir: Mem0Provider(data_dir), Path(tmp))
        self.assertTrue(report["passed"], report["checks"])


if __name__ == "__main__":
    unittest.main()
