# Mem0 OSS adapter

Pinned upstream: `mem0ai/mem0` @ `3f39fba28f7781aaf581f64a4af39d017af65835`
(v2.0.17, Apache-2.0).

## Audit summary (see `docs/research/provider-version-log.md`)

- posthog telemetry is a core dependency and defaults to ON; the adapter
  forces `MEM0_TELEMETRY=false`.
- The controlled configuration never calls an LLM: `add(..., infer=False)`
  stores messages directly. Vector store is local chroma; embedder is local
  fastembed (model downloaded once at install, offline afterwards).
- Event IDs are preserved through metadata; the adapter keeps an event-id ->
  memory-id mapping because mem0 has no delete-by-metadata API.

## Install the pinned package (for contract tests and DEV runs)

```powershell
.\.venv\Scripts\python.exe -m pip install "mem0ai[vector-stores] @ git+https://github.com/mem0ai/mem0@3f39fba28f7781aaf581f64a4af39d017af65835"
.\.venv\Scripts\python.exe -m pip install fastembed
# First use downloads the embedding model once (BAAI/bge-small-en-v1.5);
# runtime afterwards is fully offline.
```

## Run

```powershell
$env:SOVBENCH_RUN_MEM0 = "1"
uv run --frozen python -m unittest tests.contract.test_mem0_adapter -v
uv run --frozen python scripts/run_provider_dev.py --provider mem0
```

## Image

`docker/providers/mem0/Dockerfile` builds the provider image from
`python:3.12-slim` with the pinned commit and local embedding model baked in.
