# GBrain adapter

Pinned upstream: `garrytan/gbrain` @ `15b9863d13635d173562a54f55a1d388bfcf546b`
(v0.42.73.2, MIT).

## Audit summary (see `docs/research/provider-version-log.md`)

- Markdown + frontmatter in a git brain repo is the system of record; the
  PGLite database is a derived, rebuildable index.
- MIT licensed; the pinned clone is installed externally (Bun runtime +
  pinned commit), not vendored.
- Controlled configuration: PGLite engine, keyword/hybrid search with LLM
  knobs disabled, no external providers, no telemetry.
- `GBRAIN_HOME` isolates each brain; the adapter maps benchmark deletes to
  page deletion in the system of record.

## Install the pinned CLI (for contract tests and DEV runs)

```powershell
# requires Bun >= 1.3.10
bun install -g github:garrytan/gbrain   # official path; then:
gbrain doctor
```

The adapter resolves the CLI via `GBRAIN_BIN` or `gbrain` on PATH. Contract
tests are gated on `SOVBENCH_RUN_GBRAIN=1` so the suite stays green before
the pinned CLI is installed.

## Run

```powershell
$env:SOVBENCH_RUN_GBRAIN = "1"
uv run --frozen python -m unittest tests.contract.test_gbrain_adapter -v
uv run --frozen python scripts/run_provider_dev.py --provider gbrain
```

## Image

`docker/providers/gbrain/Dockerfile` builds the provider image from
`oven/bun` with the pinned commit and `bun install` at build time.
