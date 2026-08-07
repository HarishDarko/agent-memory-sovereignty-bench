"""File-backed provider registry.

Registration is impossible unless the adapter metadata validates and the
provider contract passes. Containerized providers additionally require the
executable clean-room probe to pass before registration.

AMSB extension contract: contributors add a new provider by dropping an
adapter under ``providers/<name>/``, declaring a capability manifest there,
and adding one entry to ``providers/registry.json`` with a ``factory``
reference (``module:function``). ``create_provider`` constructs the adapter
by name, so the central runner, scorer, metrics, datasets, and gold do not
need changes.
"""

from __future__ import annotations

import importlib
import json
import os
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


def _registry_path() -> Path:
    return Path(__file__).resolve().parent / "registry.json"


def create_provider(name: str, data_dir: Path | None = None, **kwargs):
    """Construct a provider adapter by registry name.

    The registry entry must contain a ``factory`` field of the form
    ``package.module:function``. Optional ``factory_kwargs_env`` maps factory
    keyword arguments to environment variable names; set environment
    variables override defaults, and unset variables pass ``None`` through to
    the factory. Unsupported names raise :class:`RegistryError`.
    """
    entry = Registry(_registry_path()).lookup(name)
    if not entry:
        raise RegistryError(f"provider {name!r} is not registered")
    factory_ref = entry.get("factory")
    if not factory_ref:
        raise RegistryError(f"provider {name!r} has no factory in the registry")
    module_name, _, function_name = factory_ref.partition(":")
    if not module_name or not function_name:
        raise RegistryError(f"provider {name!r} factory must be 'module:function'")
    module = importlib.import_module(module_name)
    factory = getattr(module, function_name)
    env_kwargs = {}
    for key, env_name in (entry.get("factory_kwargs_env") or {}).items():
        value = os.environ.get(env_name)
        if value:
            env_kwargs[key] = value
    return factory(data_dir, **{**env_kwargs, **kwargs})


def registry_entry(name: str) -> dict | None:
    """Return the raw registry entry for a provider name, if declared."""
    return Registry(_registry_path()).lookup(name)


def registered_provider_names() -> list[str]:
    """All declared provider names (baselines, controls, and integrations)."""
    return sorted(Registry(_registry_path()).registered())
