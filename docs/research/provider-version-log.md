# Provider version log

Every real provider is audited against its official upstream before any
installation. Entries record the retrieval date, the pinned commit, and the
evidence that shaped the adapter.

## OptMem - 2026-08-06

- Upstream: https://github.com/VictorTaelin/OptMem
- Pinned commit: `1fb164cf39028047781f72ac3bb1e5a691c1dcb0` (HEAD on 2026-08-06)
- License: **none present** - all rights reserved by default. The script may
  not be vendored or redistributed; the benchmark installs the pinned script
  locally (gitignored) and references it as an external dependency.
- Language/runtime: single Python 3 file (`memo`, 31,881 bytes), zero
  dependencies, standard library only. Windows-supported (msvcrt lock
  fallback).
- Network behavior: none in the tool itself; `install.sh` curls the unpinned
  `main` copy, so the benchmark pins its own copy instead. No telemetry.
- Data layout: `$MEMORY_DIR/LOG.txt` (append-only, fixed 320-byte records
  `#id YYYY-MM-DD text`), `TREE/` (rebuildable summary cache), `config`.
- Commands: `init wake note nap recall zoom forget config import`.
- Key semantics verified in source and upstream tests:
  - append-only by design; `forget` only drops tree summaries ("the log is
    never touched, so nothing is ever actually lost");
  - `recall <regex>` matches whole records, case-insensitive, capped output;
  - no temporal filtering, no tenant/principal model, no ranking;
  - `import` requires strictly ascending real dates and UTF-8;
  - record limit ENTRY_CHARS=280 bytes.
- Adapter mapping (recorded separately from upstream capabilities):
  - event IDs embedded as `[event_id]` in each memory line for provenance;
  - as-of/principal/scope filtering performed by the adapter after `recall`;
  - deletion reported as `unsupported` (a benchmark finding, not simulated);
  - snapshot/restore/export/import implemented over LOG.txt and the canonical
    event list; restart is a no-op (state is on disk).
- Pinned local install: `<repo>/.optmem/memo` (gitignored), SHA-256 recorded
  at install time.
- Built image (2026-08-06): `sovbench-optmem:1fb164c`, digest
  `sha256:bc64d013d37586253156302df506009c099a38592f26aefa5b9e383feb825833`.
  The build fetches the pinned upstream commit at build time (local use only).
- DEV verification (2026-08-06, offline reader, $0):
  - contract passes with `canary_deleted`/`error_normalization` recorded as
    `not_applicable` (append-only) and export/import + restart as `native`;
  - pre-lifecycle DEV slice (17 queries, as_of <= 2026-06-30):
    `completed_plumbing`, gold evidence recall@5 = 0.3529;
- full DEV corpus: `invalid_invariant` - OptMem cannot execute the corpus's
    required deletion lifecycle actions, which is the honest recorded finding
    for the controlled track.

## GBrain - 2026-08-06

- Upstream: https://github.com/garrytan/gbrain
- Pinned commit: `15b9863d13635d173562a54f55a1d388bfcf546b` (HEAD on 2026-08-06)
- Version: 0.42.73.2 (package.json)
- License: **MIT** (Copyright 2026 Garry Tan). Compatible with the benchmark's
  open-source plan; the pinned clone is still installed externally rather than
  vendored, keeping the benchmark repo lean.
- Runtime: Bun >= 1.3.10; TypeScript codebase (single-file compiled binary via
  `bun build --compile`, or `bun run src/cli.ts`). Not distributed on npm; the
  official install paths are `bun install -g github:garrytan/gbrain` or
  clone + `bun install` + `bun link`.
- Storage: embedded Postgres (PGLite via WASM, zero-config default) as a
  derived index; **markdown + frontmatter in a git brain repo is the system of
  record** (`docs/architecture/system-of-record.md`). `gbrain sync` +
  `gbrain extract all` rebuilds the DB from the repo; disaster recovery never
  backs up the DB.
- Isolation: `GBRAIN_HOME` redirects the brain home directory (per
  `src/core/brain-repo-durability.ts`), analogous to OptMem's MEMORY_DIR.
- Search: `gbrain search "<query>" --json` over a cheap-hybrid default with
  optional LLM knobs (`expansion`, `reranker`); the controlled adapter config
  disables LLM/network features and relies on keyword/hybrid retrieval with
  no external keys (selected on DEV only, per plan rule).
- Lifecycle: pages CRUD via put_page/delete_page ops (write-through to
  markdown); `recall`/`forget` over the derived facts table (`forget` =
  expireFact). The adapter maps benchmark deletes to page deletion in the
  system of record.
- Network behavior: many dependencies (Anthropic/OpenAI/Google SDKs,
  embeddings, rerankers) exist but are only active when providers are
  configured; the controlled configuration uses none. Telemetry: none
  observed in the audit; `gbrain doctor` and `smoke-test` are diagnostics.
- Adapter mapping (recorded separately from upstream capabilities):
  - one markdown page per event with frontmatter (event_id, principal, scope,
    available_at, authority, source, subject, kind);
  - as-of/principal/scope filtering by the adapter after search;
  - snapshot records both the git state hash of the system of record and the
    derived-index hash;
  - export = raw brain repo + manifest; import rebuilds pages and re-syncs;
  - restart is a no-op (state is on disk).
- DEV verification (2026-08-06, offline reader, $0, run 2026-08-01-042):
  - contract passes (all canaries native; deletion native);
  - full DEV corpus: `completed_plumbing`, 80 queries, gold evidence recall@5
    = 0.9861, chain-complete@5 = 0.9861 (baselines: 0.9931), authority and
    multi-hop categories at 1.0, recovery at 0.0, forbidden-evidence items
    (poison claims) present in 61 query retrievals - a measured retrieval
    behavior of the no-embedding configuration, not a pipeline artifact;
    zero cross-principal or deleted-evidence leakage.
- Operational characteristics recorded from the pinned CLI:
  - keyword search returns a fixed small top-N; the adapter unions a
    multi-word search with per-term searches;
  - the brain directory must be a git repo with committed pages (the walker
    reads git objects), so ingestion commits before sync;
  - the legacy `default` source cannot be removed; a dedicated `bench`
    source is registered and set as default;
  - Windows file locks around git objects are handled by rename-based reset
    with bounded trash reclamation.

## GBrain post-freeze supplementary local-embedding configuration - 2026-08-07

- This is an additive follow-up configuration and is not part of protocol v1
  or the frozen Task 15 results.
- Pinned GBrain source remains commit `15b9863d13635d173562a54f55a1d388bfcf546b`
  / v0.42.73.2. The pinned source contains the Ollama recipe and explicit
  `--embedding-model <provider:model>` initialization path.
- Ollama runtime: 0.32.6 standalone Windows runtime, bound to the OS-assigned
  loopback port 4713 because fixed local ports were denied by this machine.
- The initially preferred `snowflake-arctic-embed2:latest` (1.2 GB F16) was
  pulled but rejected before DEV because it stalled while loading alongside
  GBrain/PGLite on this machine. It was not scored.
- DEV candidate embedding model: `snowflake-arctic-embed:335m`, Ollama digest
  `21ab8b9b0545e26a78164a910691440a3f1de1bfa41c3953d7451d52036c581a`, 334M
  parameters, F16, 1024 dimensions, embedding capability only. DEV preflight
  passed, but DEV Recall@5 was 0.7639, below the predeclared 0.85 guardrail;
  hidden TEST was therefore not run.
- Provider configuration: `ollama:snowflake-arctic-embed:335m`, dimensions
  1024, base URL `http://127.0.0.1:4713/v1`, no hosted embedding key, no local
  generative model. The common reader remains the ledgered
  `deepseek-v4-flash` gateway.

## GBrain native completion attempts v2 - 2026-08-08

Two further local embedding candidates were evaluated on the same public DEV
split with the same pinned GBrain, preflight, and reader (see
`docs/reports/gbrain-native-local-supplement-v2.md`):

- `snowflake-arctic-embed2:latest` (digest
  `5de93a84837d0ff00da872e90830df5d973f616cbf1e5c198731ab19dd7b776b`, 566M,
  8192 context, 1024 dims): DEV Recall@5 = 0.8194.
- `bge-m3` (asserted by the pinned Ollama recipe; 8192 context, 1024 dims):
  DEV Recall@5 = 0.8056.

Both passed the optimized preflight and retrieved semantically; both remained
below the predeclared 0.85 Recall@5 guardrail (best DEV Recall@5 = 0.8194),
so hidden TEST was not run and the native track remains
`not_run` with three rejected local-embedding configurations. Cost of the two
v2 DEV attempts: USD 0.06698 (ledgered).
- Exact source/config hashes and the no-hidden-test-touch attestation are in
  the gitignored follow-up run artifact
  `runs/followups/gbrain-native-local/environment-attestation.json`.

## Mem0 OSS - 2026-08-06

- Upstream: https://github.com/mem0ai/mem0
- Pinned commit: `3f39fba28f7781aaf581f64a4af39d017af65835` (HEAD on 2026-08-06)
- Version: 2.0.17 (pyproject.toml)
- License: **Apache-2.0**
- Runtime: Python package `mem0ai` (requires-python >=3.10,<4.0); core deps
  include qdrant-client, pydantic, openai, httpx, posthog, sqlalchemy.
- Telemetry: **posthog is a core dependency and MEM0_TELEMETRY defaults to
  True** (`mem0/memory/telemetry.py`). The adapter sets `MEM0_TELEMETRY=false`
  in the provider environment; runtime egress denial is verified by the
  clean-room probe before containerized runs.
- Controlled configuration (no external LLM, no cloud):
  - `add(..., infer=False)` stores messages directly without LLM fact
    extraction (`mem0/memory/main.py`);
  - vector store: chroma (local on-disk) under the provider data dir;
  - embedder: fastembed with `BAAI/bge-small-en-v1.5` (local CPU ONNX; the
    model is downloaded once at install time and is then fully offline);
  - `MEM0_DIR` redirects the mem0 home (history.db etc.).
- Lifecycle: `delete(memory_id)` and `delete_all(user_id)` exist; the adapter
  maintains an event-id -> memory-id mapping (adapter-side registry) because
  mem0 has no delete-by-metadata API, and verifies deletion across the vector
  index and after restart.
- Metadata: `add(metadata=...)` preserves arbitrary fields; the adapter stores
  event_id, principal, scope, available_at, authority, source, subject, kind
  so raw event IDs survive through consolidation (Stage 1 diagnosis).
- Adapter mapping (recorded separately from upstream capabilities):
  - as-of/principal/scope filtering by the adapter after search;
  - snapshot hashes the logical event list plus the on-disk stores;
  - export = canonical event list + memory-id mapping; import re-adds;
  - restart is a no-op (state on disk).
- DEV verification (2026-08-06, offline reader, $0, run 2026-08-01-044):
  - contract passes (8/8 tests against the pinned package);
  - full DEV corpus: `completed_plumbing`, 80 queries, gold evidence recall@5
    = 0.9514, chain-complete@5 = 0.9444; category detail: historical/expiry/
    migration/poisoning/provenance/role_group/temporary_validity at 1.0,
    authority_conflict and multi_hop at 0.5, current_state 0.9375,
    supersession 0.875 - measured semantic-only retrieval behavior;
    forbidden (poison) items in 34 retrievals, zero cross-principal or
    deleted-evidence leakage;
  - telemetry verified disabled (module-level MEM0_TELEMETRY=False), local
    chroma store, local fastembed embeddings, zero LLM calls.
- Operational characteristics recorded from the pinned package:
  - chroma store has no keyword search (semantic-only) - informational
    message from mem0 itself;
  - metadata values must be scalar and non-null for chroma;
  - MEM0_TELEMETRY is read at import time, so the adapter sets it before any
    mem0 import;
  - chroma holds file handles on Windows; the adapter resets via mem0's
    API (memory.reset) and releases the shared system cache on cleanup.

## Hindsight - 2026-08-06

- Upstream: https://github.com/vectorize-io/hindsight
- Pinned commit: `797faf7981ce9332e2ce7c922471b72b506b4065` (HEAD on 2026-08-06)
- Version: 0.8.6 (hindsight-api / hindsight-api-slim)
- License: **MIT** (Copyright 2025 Vectorize AI, Inc.)
- Runtime: Python API server (`hindsight-api`) + worker + MCP server; deps
  include asyncpg/psycopg2/pgvector (PostgreSQL required), openai/anthropic/
  litellm providers, opentelemetry (metrics only - no posthog-style product
  telemetry observed in the audit), local embedding/reranker stack
  (sentence-transformers/torch) available, langchain text splitters.
- Architecture: banks (memory scopes) with hybrid retrieval (BM25 + semantic
  + graph + temporal decay), observations, mental models, consolidation/
  reflection (LLM), directives, webhooks, audit logs, export/import.
- Controlled configuration notes (selected on DEV only):
  - the API has a no-LLM verify mode (`memory_no_llm_verify` test fixture);
    reflection/consolidation are LLM-gated and stay OFF in the controlled
    config until the Task 13 cost gate approves gateway-routed model calls;
  - local sentence-transformers embeddings/rerankers are the offline path
    (torch stack, installed at the Phase 1 environment gate);
  - PostgreSQL+pgvector required (local `postgres:16-alpine` image exists;
    pgvector extension image needed - deferred to the environment gate).
- HTTP API surface (verified from `hindsight_api/api/http.py` at the pinned
  commit): GET /health; banks CRUD at /v1/default/banks; POST
  /banks/{id}/memories and /banks/{id}/memories/recall; DELETE
  /banks/{id}/memories (all) and per-memory observations; PATCH per memory;
  GET /banks/{id}/export; POST /banks/{id}/import; POST
  /banks/{id}/consolidate and /reflect (LLM-gated).
- **API contract confirmed against the running API (2026-08-06)**:
  - retain: `POST /v1/default/banks/{bank_id}/memories` with
    `{"items": [MemoryItem], "async": false}`; MemoryItem = content,
    ISO timestamp, `metadata: dict[str, str]`, document_id; response
    `{success, bank_id, items_count}`;
  - recall: `POST /v1/default/banks/{bank_id}/memories/recall` with
    `{query, budget, max_tokens, query_timestamp}`; results are
    `{id, text, metadata, scores.final}` (no `limit` field; `budget` is
    LOW/MID/HIGH);
  - banks list: `{"banks": [{"bank_id", ...}]}`;
  - **per-event deletion maps to cascade document deletion**
    (`DELETE /v1/default/banks/{bank_id}/documents/{event_id}`); there is no
    per-memory-unit DELETE route. Each event is stored as its own document;
  - bank reset: `DELETE /v1/default/banks/{bank_id}`.
- Environment gate (2026-08-06): API image
  `sovbench-hindsight:797faf7` built from the pinned commit
  (`#subdirectory=hindsight-api`; the repo root is a flat multi-package
  layout, and the slim base needs `git` for the pip git install);
  digest `sha256:103c6b676aae95a036875bce7478ba30b14447087f6a113402333e1d8f8f9299`.
  The server listens on **8888** (not 8000) and requires
  `HINDSIGHT_API_*` env names (`HINDSIGHT_API_DATABASE_URL`,
  `HINDSIGHT_API_LLM_PROVIDER=none`). Local embedding/reranker models
  (BAAI/bge-small-en-v1.5, cross-encoder/ms-marco-MiniLM-L-6-v2) are baked
  into `sovbench-hindsight:797faf7-cached`
  (digest `sha256:2ad9f5811b8a563f027845ef45ca76d1ec4c338f888fc8d2b925663d769d5a80`)
  with `HF_HUB_OFFLINE=1`/`TRANSFORMERS_OFFLINE=1`.
- Isolation (2026-08-06): the compose stack runs both services on an
  `internal: true` network; runtime probe from inside the API container
  confirms external HTTPS is blocked. Because published ports do not reach
  internal-network containers in this Docker version, a benchmark-owned
  alpine socat sidecar (`api-proxy`, not a provider container) forwards
  host:8000 -> api:8888.
- DEV verification (2026-08-06, offline reader, $0, run 2026-08-01-051):
  - contract passes live (6/6 adapter tests: retrieve, future exclusion,
    principal scoping, document-cascade deletion, export/import roundtrip,
    full 20-check compliance contract);
  - full DEV corpus: `completed_plumbing`, 80 queries, gold evidence
    recall@5 = **0.9792**, chain-complete@5 = **0.9722**; deletions executed
    via document cascade; zero cross-principal or deleted-evidence leakage;
  - no LLM calls (HINDSIGHT_API_LLM_PROVIDER=none); embeddings/reranking
    local CPU; telemetry: none observed (opentelemetry metrics only).
- Vendor benchmark claims (LongMemEval state-of-the-art, independently
  reproduced claims) are NOT taken as evidence here; this benchmark's DEV
  runs are the only scores recorded.
- Adapter mapping (recorded separately from upstream capabilities):
  - one bank per provider data dir; memories carry event metadata;
  - as-of/principal/scope filtering by the adapter after recall;
  - one document per event (document_id = event_id) so per-event deletion
    maps to the API's cascade document delete;
  - delete/export/import via the HTTP API (endpoint semantics to be
    confirmed against the running API at the Phase 1 environment gate);
  - snapshot hashes the logical event list plus the bank's export.
