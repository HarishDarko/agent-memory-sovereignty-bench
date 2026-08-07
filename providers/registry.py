"""File-backed provider registry.

Registration is impossible unless the adapter metadata validates and the
provider contract passes. Containerized providers additionally require the
executable clean-room probe to pass before registration.
"""

from __future__ import annotations

import json
from pathlib import Path

from providers.compliance import ProviderMeta, run_contract, validate_meta


class RegistryError(RuntimeError):
    pass


class Registry:
    def __init__(self, path: Path | str):
        self.path = Path(path)

    def _load(self) -> dict:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def register(
        self,
        meta: ProviderMeta,
        factory,
        *,
        containerized: bool = False,
        data_dir: Path | None = None,
    ) -> dict:
        errors = validate_meta(meta)
        if errors:
            raise RegistryError("invalid adapter metadata: " + "; ".join(errors))
        existing = self._load()
        if meta.name in existing:
            raise RegistryError(f"provider {meta.name!r} is already registered")
        if containerized:
            from benchmark.isolation.docker_probe import run_probe

            probe = run_probe(run_id=f"registry-{meta.name}", repo_root=self.path.parent.parent)
            if not probe["passed"]:
                return {
                    "registered": False,
                    "provider": meta.name,
                    "reason": ["docker clean-room probe failed"],
                    "probe_errors": probe["errors"],
                }
        contract = run_contract(meta, factory, data_dir or self.path.parent / ".contract-tmp")
        if not contract["passed"]:
            return {
                "registered": False,
                "provider": meta.name,
                "reason": contract["failed_checks"],
                "contract": contract,
            }
        entry = {
            "name": meta.name,
            "meta": meta.to_dict(),
            "containerized": containerized,
            "contract": {"passed": True, "checks": list(contract["checks"])},
        }
        existing[meta.name] = entry
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(existing, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return {"registered": True, "provider": meta.name}

    def lookup(self, name: str) -> dict | None:
        return self._load().get(name)

    def registered(self) -> dict:
        return self._load()
