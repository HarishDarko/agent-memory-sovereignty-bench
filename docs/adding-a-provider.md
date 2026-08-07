# Adding a Provider

This tutorial takes a competent developer from zero to a validated provider
integration without touching the central benchmark machinery.

## 1. Minimum integration (Level 1)

Copy the template:

```powershell
Copy-Item -Recurse templates\provider providers\<name>
```

Implement `adapter.py`:

- subclass `MemoryProvider` from `benchmark/providers.py`
- implement `reset`, `ingest`, `await_ready`, `retrieve`, `snapshot`,
  `restore`, `stats`, `cleanup`
- leave `delete`, `export`, `import_data`, `restart` raising
  `CapabilityNotSupported` unless supported
- provide a `make_<name>(data_dir=None, **kwargs)` factory

Example retrieval-only adapter: `templates/provider/adapter.py`.

## 2. Controlled integration

Controlled ingestion receives normalized `Event` objects. The adapter stores
them through the provider's own interface, then `retrieve(query)` returns
`RetrievalResult` with `RetrievedItem`s carrying the event metadata the
adapter wrote. Keep provider-native extraction disabled for the controlled
track (for example Mem0 `infer=False`, GBrain `--no-embedding`).

Record the exact controlled configuration in `providers/<name>/config.toml`:
upstream version, upstream commit, license, telemetry, external
dependencies, network needs, and the configuration notes.

## 3. Capability declaration

Edit `providers/<name>/manifest.toml`:

- `tracks.controlled` / `tracks.native`
- per-capability attribution: `product`, `adapter`, `runner`, `reader`,
  `scorer`, `partial`, `unsupported`

Never label a benchmark-enforced property as a product capability. If the
runner will filter results or the adapter will supply metadata, say so.

## 4. Native integration (Level 3, optional)

For the native track, expose provider-native ingestion and retrieval in the
adapter. If the native retrieval differs from the controlled path, implement
a `native_retrieve(provider, query, event_catalog)` function in the adapter
and reference it in the registry entry:

```json
"native_view": "providers.<name>.adapter:native_retrieve"
```

The central views module calls this hook when present. Without it, the
controlled `retrieve` path is used.

## 5. Lifecycle integration (Level 2, optional)

Implement any supported subset of `delete`, `export`, `import_data`,
`restart`. Map abstract delete events to the provider's native API inside
`delete(target_event_id)`. If the provider has no native delete, leave it
unsupported and say so in the manifest.

## 6. Provider-specific dependencies

Isolate dependencies:

- pip packages: add an extra to `pyproject.toml` (for example
  `[project.optional-dependencies] <name> = [...]`) and install with
  `uv sync --extra <name>`
- external binaries or servers: document in `providers/<name>/README.md` and
  `config.toml` (`external_dependencies`); gate tests with the
  `SOVBENCH_RUN_<NAME>=1` convention used by `tests/contract/`

## 7. Register and validate

Add one entry to `providers/registry.json`:

```json
"<name>": {
  "name": "<name>",
  "static": true,
  "containerized": false,
  "factory": "providers.<name>.adapter:make_<name>",
  "factory_kwargs_env": {},
  "tracks": {"controlled": true, "native": false},
  "contract_status": "declared",
  "manifest": "providers/<name>/manifest.toml",
  "meta": {
    "name": "<name>",
    "adapter_version": "0.1.0",
    "upstream_version": "<exact>",
    "upstream_commit": "<exact commit>",
    "image_digest": "n/a-local",
    "config_hash": "<sha256 of config.toml>",
    "license": "<license>",
    "telemetry": "none",
    "external_dependencies": [],
    "network_needs": []
  }
}
```

Then validate:

```powershell
uv run python scripts\validate_provider.py --provider <name>
```

Expected output:

```text
Provider: <name>
Adapter import            PASS
Reset                     PASS
Controlled ingest         PASS
Controlled retrieval      PASS
Deletion                  UNSUPPORTED
Native track              NOT IMPLEMENTED
Capability manifest       PASS
Ready for controlled DEV evaluation.
```

## 8. Tests

Add `tests/contract/test_<name>_adapter.py` modeled on
`tests/contract/test_mem0_adapter.py` (or the template test). Gate tests that
need the real provider behind `SOVBENCH_RUN_<NAME>=1` so the default suite
stays green without the provider installed.

## 9. DEV benchmark

```powershell
uv run python scripts\run_provider_dev.py --provider <name>
```

DEV uses the public corpus (`datasets/dev/personal/`) and the offline reader
at zero API cost. Confirm the run manifest records your exact pins.

## 10. Research-quality submission

Before publishing provider results:

- exact upstream commit/version in `config.toml`, registry entry, and
  manifest
- full configuration (embeddings, LLM, retrieval knobs) recorded
- deterministic setup where possible
- capability attribution filled in with evidence
- adapter-independent smoke tests for negative results (prove the interface
  works before reporting product limitations)
- run the contamination preflight and include the result

## Checklist

- [ ] `providers/<name>/adapter.py` implements `MemoryProvider`
- [ ] `providers/<name>/config.toml` has exact pins and configuration notes
- [ ] `providers/<name>/manifest.toml` attributes every capability
- [ ] registry entry added with factory and meta
- [ ] `validate_provider.py` passes (or honestly reports UNSUPPORTED)
- [ ] contract test added and env-gated
- [ ] DEV run completed with manifest
