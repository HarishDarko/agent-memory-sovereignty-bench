# Example Provider Template

Copy this directory to `providers/<name>/` and implement:

1. `adapter.py` — the `MemoryProvider` subclass and `make_<name>` factory.
2. `manifest.toml` — capability attribution (supported / unsupported /
   partial / product / adapter / runner / reader / scorer).
3. `test_adapter.py` — a contract test (see `tests/contract/` for examples).
4. `config.toml` — exact pins: upstream version, commit, license, telemetry,
   external dependencies, network needs.
5. Register the provider in `providers/registry.json` (one entry).

Then run:

```powershell
python scripts\validate_provider.py --provider <name>
```

and, once the adapter passes, the controlled DEV evaluation:

```powershell
python scripts\run_provider_dev.py --provider <name>
```

Unsupported capabilities are valid: declare them `unsupported` in the
manifest and let the adapter raise `CapabilityNotSupported`. Never fake a
product capability in the adapter.

See `docs/adding-a-provider.md` for the complete contributor tutorial.
