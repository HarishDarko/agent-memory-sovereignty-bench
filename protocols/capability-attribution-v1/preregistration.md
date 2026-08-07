# Capability Attribution Ablation v1 — Preregistration

**Status:** PREREGISTERED BEFORE HIDDEN TEST
**Date:** 2026-08-07
**Authoritative parent state:** `cdbd714e7bf8162789aa7020558917fe959d7dd7`
**Frozen Task 15 evidence:** `c3007f4`
**Protocol namespace:** `protocols/capability-attribution-v1/`
**Run namespace:** `runs/followups/capability-attribution-v1/`
**Public report:** `docs/reports/capability-attribution-v1.md`

This is an additive experiment. It does not modify or recompute Task 15 controlled/native results or corrected Semantic Exit evidence. The broad memory roadmap remains stopped.

## 1. Research questions

**Primary RQ:** When a memory benchmark supplies governance semantics outside the memory product, how much can those supplied semantics change measured correctness?

**RQ2:** Which governance properties are most sensitive to benchmark assistance?

**RQ3:** Can a benchmark report a successful capability when the memory product does not natively represent or enforce it?

**RQ4:** Which layer implements each observed capability: product, adapter, runner, reader, or scorer?

## 2. Hypotheses

All effects are defined as assisted minus unassisted.

- **H-AUTH:** Supplying benchmark authority/source metadata and governance-aware instructions increases authority-conflict correctness by at least 0.05 and reduces wrong-authority selection.
- **H-PROV:** Supplying benchmark source/provenance metadata and governance-aware instructions increases source/provenance correctness by at least 0.05.
- **H-TEMP:** Benchmark `available_at <= as_of` and scope/current-history eligibility filtering increases temporal answer correctness by at least 0.05 or changes future-evidence leakage from nonzero to zero.
- **H-SCOPE:** Benchmark principal/scope post-filtering reduces cross-principal evidence exposure or unauthorized answering, including a material `>0 -> 0` leakage transition where present.
- **H-DELETE:** Product-native deletion, not scorer suppression, is responsible for deleted evidence becoming unavailable. Adapter lifecycle mapping may contribute by translating abstract delete events to provider APIs.
- **H-NULL:** For any property, assisted and unassisted conditions differ by less than 0.05 and show no qualitative leakage transition.

Failure to reject H-NULL is an acceptable negative result and ends the memory research phase.

## 3. Providers and pinned configurations

No provider is upgraded or patched.

| Provider | Pinned upstream | Version | Controlled configuration used here |
|---|---|---|---|
| GBrain | `15b9863d13635d173562a54f55a1d388bfcf546b` | `0.42.73.2` | PGLite, `--no-embedding`, keyword search, adapter-written Markdown/frontmatter |
| Mem0 OSS | `3f39fba28f7781aaf581f64a4af39d017af65835` | `2.0.17` | `infer=False`, local Chroma, FastEmbed `BAAI/bge-small-en-v1.5`, telemetry disabled |
| Hindsight | `797faf7981ce9332e2ce7c922471b72b506b4065` | `0.8.6` | LLM features off, local embeddings/reranker, one isolated bank per pack run |

Provider-native extraction is not enabled because it would confound the layer ablation. The study asks what benchmark assistance changes while source memories and provider state stay fixed.

## 4. Dataset and exact query selection

The existing hidden TEST packs remain the only TEST data. Commitment file SHA-256: `460598a95ca9567fa392dc287cc63e859494586f060d69ea22179cfeb2119a5d`.

Selection is category- and generator-position-based. It was fixed without inspecting provider outcomes. Apply the following IDs independently to each prefix `pack1`, `pack2`, and `pack3`:

| Property | Query kinds | Exact suffixes in each pack |
|---|---|---|
| Authority | `authority_conflict`, `poisoning` | `query_0050`, `query_0051` |
| Provenance | `provenance` | `query_0056` |
| Temporal | first two fixed storylines, all temporal categories | `query_0001` through `query_0012` inclusive |
| Scope/isolation | `role_group`, `cross_user` | `query_0054`, `query_0055`, `query_0059` |
| Deletion | `deletion`, `do_not_store` | `query_0052`, `query_0053` |

The temporal suffix mapping is fixed as:

- current state: `0001`, `0007`
- historical state: `0002`, `0008`
- supersession: `0003`, `0009`
- changed preference: `0004`, `0010`
- temporary validity: `0005`, `0011`
- expiry: `0006`, `0012`

Total unique TEST queries: 60 (20 per pack). The same selection rule is used on DEV by query kind and the first two lexical subject IDs; DEV is for implementation validation only.

## 5. Fixed state and retrieval design

For each provider and pack:

1. Start clean and isolated.
2. Ingest all non-delete source events in one controlled batch.
3. Apply every existing delete/do-not-store event through the provider's native delete API using the existing adapter lifecycle mapping.
4. Freeze one final provider snapshot/state hash.
5. Retrieve every paired condition from that same state without mutation.
6. Verify the state hash before and after every query.

Building one final state intentionally allows earlier-as-of queries to expose later events in the native/raw temporal condition. The assisted condition filters the same raw result by benchmark temporal eligibility. This isolates benchmark filtering and does not claim to reproduce the frozen V1 checkpoint runner.

## 6. Evidence and prompt conditions

### Authority and provenance 2×2

The retrieved item order, IDs, text, scores, token budget, query, model, seed, and replicate index are identical across cells.

| ID | Metadata | Prompt |
|---|---|---|
| `M0P0` | `id`, `score`, `text` only | neutral prompt |
| `M1P0` | standard benchmark governance metadata | neutral prompt |
| `M0P1` | `id`, `score`, `text` only | governance-aware frozen reader prompt |
| `M1P1` | standard benchmark governance metadata | governance-aware frozen reader prompt |

`M0P0 -> M1P1` is the primary contrast. `M0P0 -> M1P0` estimates metadata without instruction. `M0P0 -> M0P1` estimates instruction without metadata. The interaction is reported descriptively as `(M1P1-M0P1) - (M1P0-M0P0)`.

The standard governance prompt is `prompts/reader-v1.md`, SHA-256 `5eab2ba89728e2af16293868703b9e005be6137a43b2a4f2505bb910b3e891fa`. The neutral prompt is frozen in `protocols/capability-attribution-v1/neutral-reader-v1.md`, SHA-256 `8fa90804ccbe74a77228646a748829a392b8140d451b17785451551d8cf817fe`.

### Temporal conditions

- `C0-native`: product-native/raw retrieval mapped to opaque evidence IDs; no benchmark as-of, current/history, principal, or scope post-filter beyond parameters the product API fundamentally requires.
- `C1-assisted`: the same raw result filtered by `available_at <= query.as_of`, `principal == query.principal`, and requested scope equality.

GBrain and Mem0 receive the paired C0/C1 analysis. Mem0's C0 retains its native `user_id` search filter because that is a product interface. Hindsight is descriptive only: pinned recall requires application-supplied `query_timestamp`, so a parameter-free C0 is not a meaningful supported configuration.

### Scope conditions

- `D0-native`: provider's own native principal/bank semantics only; no benchmark principal/scope post-filter.
- `D1-assisted`: same raw result plus benchmark principal and scope filtering.

GBrain, Mem0, and Hindsight are included. Mem0 retains native `user_id`; GBrain CLI and the tested Hindsight bank do not independently enforce benchmark principal/scope metadata.

### Deletion attribution

No artificial no-delete condition is created. For each provider the report records:

1. native delete mechanism;
2. adapter mapping from abstract delete event to product API;
3. deleted target retrieval under native/raw retrieval after deletion;
4. any additional benchmark filtering contribution.

Deletion is descriptive unless a clean paired difference emerges without withholding the product delete call.

## 7. Reader and execution freeze

- Model alias: `deepseek-v4-flash`
- Expected dated release: `DeepSeek-V4-Flash-0731`; rolling alias is reported unless response evidence identifies the checkpoint
- Temperature: `0.0`
- Thinking/reasoning: disabled / none
- Evidence token budget: `2048`
- Repeats: `3` per query-condition-provider
- Max retries: `2`
- Stateless requests: exactly two messages, no conversation history
- Gateway: existing policy-gated DeepSeek proxy with identity stamping and ledger
- Scoring: existing typed scorer and private gold; no gold is passed to providers or readers

Planned reader calls: 918 maximum before bounded retries:

- authority/provenance: 9 queries × 4 cells × 3 providers × 3 repeats = 324
- temporal: 36 queries × 2 conditions × 2 providers × 3 repeats = 432
- scope: 9 queries × 2 conditions × 3 providers × 3 repeats = 162

Deletion attribution uses deterministic retrieval and no additional reader calls.

## 8. Metrics

No aggregate governance score is created.

### Authority

- typed answer correctness;
- wrong-authority selection: incorrect answer with cited external/poison evidence;
- abstention rate;
- paired correctness delta and answer-change rate.

### Provenance

- typed source/provenance correctness;
- explicit source classification correctness where gold exists;
- abstention rate;
- paired correctness delta and answer-change rate.

### Temporal

- current-state accuracy (`current_state`, `changed_preference`, `temporary_validity`, `expiry` reported separately);
- historical-state accuracy;
- supersession accuracy;
- future-evidence count (`available_at > as_of`);
- future-information answer leakage;
- paired delta and evidence-set change rate.

### Scope

- cross-principal evidence count;
- wrong-scope evidence count;
- unauthorized answer rate on gold-abstain cases;
- answer correctness;
- paired delta and evidence-set change rate.

### Deletion

- deleted target evidence retrieved after native delete;
- product-native delete outcome;
- adapter lifecycle mapping outcome;
- benchmark filtering contribution.

## 9. Statistical procedure

- Pairing unit: identical provider, pack, query, and replicate.
- Primary accuracy estimate: mean over all attempts.
- Exact McNemar: first attempt per query, preserving one binary observation per query.
- Bootstrap: existing paired block bootstrap, 10,000 resamples, seed `20260805`, 95% interval; block = `pack:subject` (or `pack:query_id` for corpus-level specials).
- Multiple comparisons: Holm-Bonferroni within each property family across declared primary provider contrasts.
- Reliability: pass@1 and all-success rate across three repeats.
- Absolute effect size: assisted accuracy minus native/unassisted accuracy.
- Answer-change rate and evidence-set Jaccard/difference are descriptive.

A capability-attribution effect is **material** only if:

1. Holm-adjusted p < 0.05 where applicable;
2. the 95% block-bootstrap interval excludes 0;
3. exact McNemar has at least 5 discordant pairs;
4. absolute correctness delta is at least 0.05.

For unauthorized, future, or deleted evidence counts, a clear transition between zero and nonzero may be material despite limited significance power. Provenance has only three TEST queries and is declared underpowered for statistical resolution; it remains quantitative/descriptive and cannot independently satisfy the full significance rule.

## 10. Analysis plan

1. Validate query IDs, kinds, counts, uniqueness, pack coverage, and commitment hashes.
2. Validate one-provider-per-run isolation, state hashes, read-only retrieval, and no gold access.
3. Produce blind condition IDs for first-pass analysis.
4. Compute per-attempt rows, then per-query and per-property summaries.
5. Compute paired deltas, bootstrap intervals, exact McNemar, Holm adjustments, reliability, answer changes, evidence changes, and leakage counts.
6. Apply the materiality rule exactly once.
7. Unblind labels only after automated QA passes.
8. Attribute each capability to product, adapter, runner, reader, and scorer using the fixed vocabulary: `PRIMARY`, `CONTRIBUTES`, `VERIFIES`, `NOT INVOLVED`, `NOT OBSERVABLE`, `UNSUPPORTED`.
9. Report negative results and unsupported provider/property combinations without replacement experiments.

## 11. DEV validation and TEST gate

DEV must prove:

- exact condition construction and single-layer differences;
- identical text/order across A/B 2×2 cells;
- raw/assisted evidence derivation from one retrieval call for C/D;
- private gold never appears in provider or reader inputs;
- reader requests are stateless and ledgered;
- deterministic selection, hashes, and analysis;
- state hash unchanged by retrieval;
- deletion attribution does not suppress evidence in the scorer.

DEV values cannot alter providers, query selection, prompts, metrics, thresholds, or analysis after this preregistration commit. A technical correction after TEST access must be recorded in `deviations.md`, preserve the original attempt, and cannot be chosen based on scores.

## 12. Stop conditions

Stop the affected run, preserve evidence, and report the reason if:

- dataset commitment or exact query-kind mapping fails;
- provider pin/config differs;
- gold is readable by provider or reader;
- pre/post retrieval state hashes differ;
- paired cells differ in more than the declared layer;
- gateway identity/statelessness fails;
- run artifacts cannot be hashed;
- total incremental API cost reaches USD 2.00.

One provider failure does not authorize substitution or expansion. Continue only the already-preregistered meaningful cells.

## 13. Cost ceiling

Hard experiment ceiling: **USD 2.00 incremental API cost**, enforced fail-closed by the existing gateway/cost accounting. Expected cost is substantially lower because only the common reader uses the API; controlled providers make no native LLM calls. Cost is accounting, not a provider-performance criterion.

## 14. Claims policy and final stop

If a material effect is observed, the maximum claim is:

> Some measured memory-governance capabilities depend materially on benchmark-supplied semantics, so benchmark results should explicitly attribute capabilities to product, adapter, runner, reader, and scorer layers.

The claim is limited to tested properties, provider pins, corpus, prompt, and reader.

If no material effect is observed, the negative result is final. No provider, model, dataset, or framework is added. After the report, publication decision, review package, provider summaries, tests, and final commit, all memory research stops.
