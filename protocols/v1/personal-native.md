# Memory Sovereignty Benchmark — Protocol v1 (Personal, Product-Native Track)

**Status:** PREREGISTERED 2026-08-06, alongside the frozen controlled track
(`personal-controlled.md`). Execution follows Task 15 of the implementation
plan. Native outcomes are published **beside** the controlled track, never
merged into a combined leaderboard.

## 1. Purpose

The product-native track measures each provider under its *intended native
configuration* from official upstream documentation, under the same
clean-room, manifest, failure, and statistical rules as the controlled track.
It answers: how does a provider behave when its own features (LLM fact
extraction, consolidation/reflection, default retrieval) are enabled?

No preference exists for either track before the data is analyzed. Native
configurations are preregistered here; none may be tuned after TEST results
are seen.

## 2. Track separation

- Same hidden TEST packs, same frozen reader (DeepSeek-V4-Flash-0731
  expectation, rolling attestation, no thinking, temp 0.0, 3 replicates).
- Same deterministic clock, per-query baseline-hash and mutation checks,
  ledgered gateway, blinded QA, and redacted reports.
- Provider-native model calls (LLM extraction, consolidation, reflection)
  are routed **only** through the benchmark gateway (ledgered, identity
  stamped, no direct egress from provider containers) — the same isolation
  contract as the controlled track.
- Report files: `reports/protocol-v1/personal-native.{json,csv,md}`;
  run artifacts under `runs/protocol-v1/native/`.

## 3. Preregistered native configurations (official sources, 2026-08-06)

### OptMem (native = raw tool semantics)

- The tool is a flat append-only log with regex recall: no temporal
  filtering, no tenant/principal model, no ranking.
- Native configuration: adapter-side as-of/principal/scope filtering
  **disabled** (`filtering=False`), so recall returns everything matching
  the regex from the ingested log. Cross-user and scope behavior is
  therefore measured as the tool itself behaves.
- Deletion remains unsupported (append-only) — recorded as `unsupported`,
  runs invalidating on required lifecycle actions are `invalid_invariant`.

### GBrain (native)

- Official native retrieval uses an embedding provider (ZeroEntropy default;
  OpenAI/Voyage alternatives) plus optional LLM query expansion and a
  hosted reranker.
- **Not run in this environment**: no embedding-provider credential is
  available (the only API key is the DeepSeek key, which offers no
  embeddings endpoint). Recorded as `not_run` with this reason; no score,
  no zero.

### Mem0 OSS (native)

- Official native config: LLM fact extraction (`add(..., infer=True)`) with
  a configured LLM, an embedding model, and a vector store.
- Preregistered configuration:
  - LLM: OpenAI-compatible provider via the benchmark gateway
    (`base_url` = local gateway proxy, `model` = `deepseek-v4-flash`,
    key = the benchmark's DeepSeek key), temperature 0.0; every extraction
    call is ledgered.
  - Embedder: `fastembed` `BAAI/bge-small-en-v1.5` (local, offline) —
    deviation recorded: mem0's default embedder is OpenAI's
    text-embedding-3-small, which requires an OpenAI credential we do not
    hold; the local embedder keeps the run fully offline and egress-free.
  - Vector store: chroma (local, same as controlled) — deviation recorded
    (mem0's default is Qdrant).
  - Telemetry: `MEM0_TELEMETRY=false` (same as controlled).

### Hindsight (native)

- Official native config enables LLM-gated memory features: fact
  extraction/retain with LLM, consolidation, and reflection.
- Preregistered configuration: `HINDSIGHT_API_LLM_PROVIDER=openai`,
  `HINDSIGHT_API_LLM_MODEL=deepseek-v4-flash`,
  `HINDSIGHT_API_LLM_BASE_URL=http://api-proxy:9000/v1` (benchmark-owned
  socat bridge to the host gateway), `HINDSIGHT_API_LLM_API_KEY` = the
  gateway key; every LLM call is ledgered. The API container remains on the
  internal egress-free network; its only external route is the gateway
  bridge.

## 4. Execution rules

- One provider at a time; fresh run-scoped state; same 576-attempt-per-
  participant structure (3 packs x 3 replicates x 64 queries).
- Failed attempts (timeouts, invalid JSON, tool errors) stay in the
  denominator; runs failing invariants are `invalid_invariant` with
  evidence preserved.
- The reader is identical to the controlled track; controls (oracle,
  no-memory, random, BM25 baselines) are not re-run because they measure
  the reader and harness, not provider-native behavior; the controlled
  track already validated them on the same packs.
- Cost is recorded per participant from the ledger as pure accounting.

## 5. Analysis

Same frozen statistics and decision labels (resolved/unresolved/
unsupported/invalid). Native comparisons are reported only within the
native track and against each provider's own controlled numbers for
reference — never as a merged leaderboard.

## 6. Publication

Redacted reports only; no winner narrative; limitations include the
deviation list above (embedder/store choices, single reader model, rolling
alias attestation).
