"""Provider adapter compliance contract and registry gate."""

import tempfile
import unittest
from pathlib import Path

from benchmark.config import load_settings
from benchmark.events import Event
from benchmark.schema import SchemaError, validate_provider_capabilities
from providers.bm25 import SqliteFtsProvider
from providers.full_context import FullContextProvider
from providers.registry import Registry, RegistryError
from providers.compliance import ProviderMeta, run_contract, validate_meta


def _meta(name="test-provider", **overrides):
    values = dict(
        name=name,
        adapter_version="0.1.0",
        upstream_version="1.2.3",
        upstream_commit="abc123",
        image_digest="sha256:deadbeef",
        config_hash="h" * 64,
        license="MIT",
        telemetry="none",
        external_dependencies=[],
        network_needs=[],
    )
    values.update(overrides)
    return ProviderMeta(**values)


class TestMetaValidation(unittest.TestCase):
    def test_valid_meta_passes(self):
        self.assertEqual(validate_meta(_meta()), [])

    def test_missing_license_or_telemetry_rejected(self):
        self.assertTrue(any("license" in error for error in validate_meta(_meta(license=""))))
        self.assertTrue(any("telemetry" in error for error in validate_meta(_meta(telemetry="unknown"))))


class TestCapabilitySchema(unittest.TestCase):
    def test_capability_record_passes_schema(self):
        record = {
            "capabilities": {
                "supports_snapshot": True,
                "supports_restore": True,
                "supports_delete": True,
                "supports_export": False,
                "supports_import": False,
                "supports_restart": False,
                "read_only_retrieval": True,
                "uses_ground_truth": False,
                "network_required": False,
                "async_indexing": False,
            },
            "meta": _meta().to_dict(),
        }
        validate_provider_capabilities(record)

    def test_unknown_capability_key_rejected(self):
        record = {
            "capabilities": {"supports_snapshot": True, "magic_mode": True},
            "meta": _meta().to_dict(),
        }
        with self.assertRaises(SchemaError):
            validate_provider_capabilities(record)


class TestContract(unittest.TestCase):
    def test_sqlite_fts_passes_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = run_contract(_meta(name="bm25-sqlite-fts"), lambda data_dir: SqliteFtsProvider(data_dir, k=10), Path(tmp))
        self.assertTrue(report["passed"], report["checks"])
        failed = [name for name, check in report["checks"].items() if check["outcome"] == "failed"]
        self.assertEqual(failed, [])
        self.assertEqual(report["checks"]["export_import"]["outcome"], "unsupported")
        self.assertEqual(report["checks"]["restart"]["outcome"], "unsupported")

    def test_full_context_passes_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = run_contract(_meta(name="full-context"), lambda data_dir: FullContextProvider(data_dir), Path(tmp))
        self.assertTrue(report["passed"], report["checks"])

    def test_mutating_provider_fails_read_only_check(self):
        class MutatingProvider(FullContextProvider):
            def retrieve(self, query):
                result = super().retrieve(query)
                self._events.append(
                    Event("mutated", "2026-12-31T00:00:00Z", "user_001", "personal", "system", "test", "boom", subject="person_01")
                )
                return result

        with tempfile.TemporaryDirectory() as tmp:
            report = run_contract(_meta(name="mutating"), lambda data_dir: MutatingProvider(data_dir), Path(tmp))
        self.assertFalse(report["passed"])
        self.assertEqual(report["checks"]["read_only_retrieval"]["outcome"], "failed")

    def test_canaries_detect_future_cross_user_authority_multi_hop_and_delete(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = run_contract(_meta(name="canary"), lambda data_dir: SqliteFtsProvider(data_dir, k=10), Path(tmp))
        for check in ("canary_future", "canary_cross_user", "canary_authority", "canary_multi_hop", "canary_deleted"):
            self.assertEqual(report["checks"][check]["outcome"], "native", report["checks"][check]["details"])


class TestRegistry(unittest.TestCase):
    def test_registration_requires_passing_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry = Registry(Path(tmp) / "registry.json")
            registry.register(_meta(name="broken"), lambda data_dir: MutatingProviderForRegistry(data_dir))
            self.assertEqual(registry.registered(), {})

    def test_register_and_lookup_baseline(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry = Registry(Path(tmp) / "registry.json")
            meta = _meta(name="bm25-sqlite-fts")
            registry.register(meta, lambda data_dir: SqliteFtsProvider(data_dir, k=10))
            self.assertIn("bm25-sqlite-fts", registry.registered())
            self.assertEqual(registry.lookup("bm25-sqlite-fts")["name"], "bm25-sqlite-fts")

    def test_duplicate_registration_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry = Registry(Path(tmp) / "registry.json")
            registry.register(_meta(name="x"), lambda data_dir: FullContextProvider(data_dir))
            with self.assertRaises(RegistryError):
                registry.register(_meta(name="x"), lambda data_dir: FullContextProvider(data_dir))


class MutatingProviderForRegistry(FullContextProvider):
    def retrieve(self, query):
        result = super().retrieve(query)
        self._events.append(
            Event("mutated", "2026-12-31T00:00:00Z", "user_001", "personal", "system", "test", "boom", subject="person_01")
        )
        return result


if __name__ == "__main__":
    unittest.main()
