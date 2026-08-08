# OptMem adapter

Pinned upstream: `VictorTaelin/OptMem` @ `1fb164cf39028047781f72ac3bb1e5a691c1dcb0`.

## Requirements at a glance

- Install: copy the pinned upstream script to a local, gitignored location
  (see "Local pinned install" below); no pip dependencies
- External services: none (single-file Python CLI, no network)
- Environment: `SOVBENCH_OPTMEM_MEMO` / `OPTMEM_MEMO_PATH` or `memo` on PATH
- Controlled support: yes
- Native support: no (not implemented)
- Lifecycle support: deletion unsupported by design (append-only); export/
  recovery partial
- Licensing: upstream has **no license file** (all rights reserved by
  default). No OptMem source is vendored or redistributed; do not publish a
  prebuilt OptMem image unless redistribution rights are clarified
- Validation: `uv run python scripts/validate_provider.py --provider optmem`

## Audit summary (see `docs/research/provider-version-log.md`)

- Single-file Python 3 CLI, zero dependencies, no network, no telemetry.
- **No license file** - all rights reserved by default. The pinned script is
  installed locally and is never vendored into or redistributed from this
  repository.
- **Append-only by design**: `forget` drops a rebuildable tree summary; log
  records are never edited or deleted. The adapter reports deletion as
  `unsupported`, which is a real benchmark finding, not a simulated feature.
- No temporal filtering, tenant model, or ranking in `recall`. The adapter
  performs as-of, principal, and scope filtering and embeds event IDs in each
  memory line for provenance mapping.

## Local pinned install (used by contract tests and DEV runs)

```powershell
New-Item -ItemType Directory -Force .optmem | Out-Null
Copy-Item "$env:TEMP\optmem-audit\memo" .optmem\memo   # from the pinned clone
```

The adapter resolves the script via `SOVBENCH_OPTMEM_MEMO` / `OPTMEM_MEMO_PATH`
or `memo` on PATH.

## Run the adapter contract and a retrieval-only DEV run

```powershell
uv run --frozen python -m unittest tests.contract.test_optmem_adapter -v
uv run --frozen python scripts/run_provider_dev.py --provider optmem
```

## Image

`docker/providers/optmem/Dockerfile` builds the provider image with the pinned
commit fetched at build time (local use only). The containerized run wiring is
part of the provider-run orchestrator.
