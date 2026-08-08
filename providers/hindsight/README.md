# Hindsight adapter

Pinned upstream: `vectorize-io/hindsight` @
`797faf7981ce9332e2ce7c922471b72b506b4065` (v0.8.6, MIT).

## Requirements at a glance

- Install: Docker; build/run the pinned stack
  (`docker/providers/hindsight/docker-compose.yml`), which bakes the local
  model cache; no prebuilt image is published
- External services: PostgreSQL + pgvector (in the compose stack); provider
  LLM features off in the controlled configuration
- Environment: `HINDSIGHT_API_URL` (default `http://127.0.0.1:8000`)
- Controlled support: yes
- Native support: yes (declared in `manifest.toml`); temporal ownership is
  descriptive because recall requires an application-supplied
  `query_timestamp`
- Lifecycle support: deletion native; whole-bank export/import yes
- Research limitation: provenance partly adapter-supplied; principal/scope
  isolation is runner-assisted in this benchmark
- Validation: `uv run python scripts/validate_provider.py --provider hindsight`
  (with the stack running)

## Audit summary (see `docs/research/provider-version-log.md`)

- Hindsight is an API-server memory system (hybrid BM25 + semantic + graph +
  temporal decay) over PostgreSQL + pgvector. The adapter is an HTTP client.
- No posthog-style product telemetry observed; opentelemetry is metrics-only.
- Controlled configuration keeps LLM features off (reflection/consolidation
  are LLM-gated) until the Task 13 cost gate; local embeddings/rerankers are
  the offline path at the Phase 1 environment gate.
- Hindsight's own LongMemEval claims are not treated as evidence here; only
  this benchmark's DEV runs count.

## Run the API (Phase 1 environment gate)

```powershell
docker compose -f docker/providers/hindsight/docker-compose.yml up -d
$env:HINDSIGHT_API_URL = "http://127.0.0.1:8000"
$env:SOVBENCH_RUN_HINDSIGHT = "1"
uv run --frozen python -m unittest tests.contract.test_hindsight_adapter -v
```

## Adapter notes

Request/response shapes were read from the pinned source and must be
confirmed against the running API before scored use. Per-memory deletion
semantics are part of that confirmation.
