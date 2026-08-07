# Memory Sovereignty Benchmark — Protocol v1 (Personal, Controlled Track)

**Status:** FROZEN. Tag `protocol-v1-freeze` (local only). Any code or config
change that can affect scores after this freeze creates a new benchmark
version and invalidates the unopened/partially opened run.

**Source of truth:** the canonical research plan (Notion), this repository's
`SPEC.md`, and the executed record in `docs/progress/implementation.json`.
This document supersedes earlier design notes only where the executed
harness proves them wrong; every deviation is recorded in the progress
record, never silently edited.

## 1. Purpose and claims policy

The benchmark measures memory-system correctness, governance, lifecycle
behavior, and portability on synthetic personal memory workloads, under a
fail-closed isolation contract. Results are the only output: no preference
for or against any system exists before the frozen data is analyzed. This
document does not declare winners; `analysis-plan.md` defines how
comparisons are labeled.

Claims made from this protocol are limited to:

- retrieval quality against hidden structured gold (evidence recall and
  complete-chain);
- typed answer correctness of a stateless reader fed bounded, auditable
  evidence;
- abstention calibration, authority handling, and leakage behavior;
- deletion persistence and export/import round-trip behavior as measured by
  the adapter contract and lifecycle runs;
- operational cost and latency from the ledgered runs.

Provider marketing claims, upstream leaderboards, and reproduction claims by
providers are not evidence in this benchmark.

## 2. Scope: controlled track only

This protocol covers the **controlled track** (one provider, one frozen
configuration, no provider-native LLM features). The product-native track is
defined separately in `personal-native.md` (Task 15) and is reported beside,
never merged with, the controlled track. There is no combined leaderboard.

## 3. Isolation and environment contract

Every scored run must satisfy the clean-room contract (repository rules,
`AGENTS.md`; enforced by `contamination/preflight.py` and the Docker policy
probe):

1. One provider per run; no cross-provider volumes, databases, caches, or
   networks. Provider state lives in a run-scoped volume.
2. Provider containers have no uncontrolled internet egress. The only
   external route is the policy-gated model gateway, and only for the
   allowlisted upstream host.
3. Gold answers, hidden TEST packs, scorer code expectations, and acceptable
   answers are never mounted into, copied into, or readable by provider or
   reader runtimes.
4. Deterministic benchmark clock only (`clock_start =
   2026-08-01T00:00:00Z`); no wall-clock "today" in scoring.
5. Retrieval is read-only or snapshot-isolated: restore from the checkpoint
   baseline, snapshot before and after, and any restore hash mismatch or
   query-time mutation invalidates the run before reader/scorer use.
6. Telemetry is disabled where upstream allows and runtime denial is proven
   by the clean-room probe; denial is never inferred from config alone.
7. The reader is stateless: a single request, exactly two messages, no
   conversation history, token budget 2048.

Preflight checks (`contamination/preflight.py`) run before every scored run:
network egress, compose policy, gold inaccessibility, no-memory control,
oracle control, canary isolation, cross-user isolation, future leakage,
query mutation, fresh state, reader statelessness. Any required check that
fails aborts the run (`aborted_preflight`).

## 4. Reader protocol (frozen by the approved pilot)

The stateless reader was calibrated by a cost-gated pilot
(`experiments/reader-pilot/protocol.md`, live run 2026-08-06, USD 0.0258,
180 requests) and the setting below is frozen into
`config/default.toml`:

| Setting | Frozen value |
|---|---|
| Model alias | `deepseek-v4-flash` |
| Expected dated release | `DeepSeek-V4-Flash-0731` |
| Attestation | `rolling` (results labeled "rolling alias observed on DATE", never the 0731 checkpoint, unless the returned model evidences the release) |
| Thinking | disabled |
| Reasoning effort | `none` |
| Temperature | 0.0 |
| Token budget (evidence bundle) | 2048 |
| Prompt | `prompts/reader-v1.md`, version v1 |
| Repeats per query | 3 |
| Max messages | 2 (stateless) |
| Max retries | 2 |
| Endpoint | official DeepSeek API through the policy-gated proxy; every request ledgered |

Reader selection was decided by the preregistered hierarchy
(JSON validity, oracle correctness, abstention correctness, evidence-ID
validity, mean tokens) and the pilot data. No reader setting may be changed
after this freeze.

## 5. Datasets

### DEV split (public, committed)

- `datasets/dev/personal/` — 105 events, 80 queries, 80 gold rows; seed
  `20260805`; generator `benchmark/datasets/generator_v2.py`.
- All content is synthetic and generated after the reader checkpoint release
  date; nothing derives from real personal data or provider training data.
- Used only for adapter development, config selection, and plumbing
  verification. Every number produced from DEV is plumbing evidence, not a
  benchmark result.

### Hidden TEST split (private, unopened)

- Three packs of 64 queries (192 total) at `scorer_private/test-v1/`
  (gitignored), generated from an unrevealed master seed.
- Only the SHA-256 commitments are committed
  (`datasets/commitments/test-v1.json`); the freeze verifies pack contents
  against those commitments.
- The hidden TEST remains unopened until this freeze tag exists. After the
  freeze, no code or config change that can affect scores is allowed; any
  such change invalidates the run.
- Value pools for answers are disjoint between DEV and every TEST pack;
  split isolation is audited by `scripts/audit_dataset.py`.

## 6. Participants

### Controls (executed first, in this order)

| Control | Role | Expected behavior |
|---|---|---|
| `no-memory` | Abstention control | Always abstains; abstain accuracy 1.0 required |
| `oracle` | Retrieval integrity | Perfect evidence; recall@5 = 1.0 required |
| `random-retrieval` | Chance baseline | Seeded deterministic; DEV recall@5 ≈ 0.111 |
| `full-context` | No-retrieval cost control | Recency-ordered, filtered |
| `bm25-pure` | Lexical baseline | DEV recall@5 = 0.9931 |
| `bm25-sqlite-fts` | Lexical baseline | DEV recall@5 = 0.9931 |

### Providers (one per run, fresh run-scoped state)

| Provider | Pinned upstream | Version | License | Controlled config |
|---|---|---|---|---|
| OptMem | `1fb164cf39028047781f72ac3bb1e5a691c1dcb0` | 0.1.0 (script) | none present (local gitignored install) | adapter-side filtering; deletion recorded unsupported |
| GBrain | `15b9863d13635d173562a54f55a1d388bfcf546b` | 0.42.73.2 | MIT | `init --pglite --no-embedding`; keyword/hybrid only |
| Mem0 OSS | `3f39fba28f7781aaf581f64a4af39d017af65835` | 2.0.17 | Apache-2.0 | `add(infer=False)`; local chroma + fastembed; `MEM0_TELEMETRY=false` pre-import |
| Hindsight | `797faf7981ce9332e2ce7c922471b72b506b4065` | 0.8.6 | MIT | LLM-gated reflection/consolidation OFF; local embeddings/rerankers; admission gated on the Phase 1 environment (Postgres+pgvector) and API verification |

All pins and retrieval-date evidence are in
`docs/research/provider-version-log.md`. Provider images are pinned by
digest where built (see `config-freeze.json`). Capability outcomes are one
of `native | adapter | unsupported | not_applicable | failed` and are
recorded, never faked.

## 7. Execution design

1. Verify the clean tree, the freeze hashes, and the unopened TEST
   commitment (`scripts/freeze_protocol.py --verify`).
2. Run controls first: no-memory, oracle, random-retrieval, full-context,
   pure BM25, SQLite FTS.
3. Run providers one at a time: OptMem, GBrain, Mem0 OSS, Hindsight, each on
   a fresh run-scoped volume with the frozen configuration.
4. For each query: replay events up to the query's `as_of`, restore the
   provider to the checkpoint baseline, snapshot, retrieve, snapshot again
   and verify no mutation, budget the evidence to 2048 tokens, send one
   stateless reader request, score against hidden gold.
5. Each query is repeated 3 times (frozen repeat count). Repeats use fresh
   restore-from-baseline so attempts are independent.
6. The deterministic analysis runs on blinded provider IDs first; QA signs
   off before unblinding (`analysis-plan.md`).

Run artifacts (manifests, traces, scores, gateway logs, ledger) land under
`runs/protocol-v1/<provider>/` and are immutable once written; result
bundles are emitted after analysis.

## 8. Metrics and primary outcomes

Metric families are declared in `benchmark/metrics.py`: retrieval, reader,
reliability, operational. Primary outcomes, each with one preregistered
definition:

1. **Complete-chain@5** — fraction of non-abstain queries where the top-5
   retrieved set contains the entire gold evidence chain (multi-hop chains
   require every link).
2. **Typed answer correctness** (`reader_accuracy`) — fraction of queries
   where the reader's structured answer matches typed gold
   (exact/set/date/bool/quantity, private acceptable aliases), with
   abstentions scored per gold.
3. **Calibrated abstention** (`abstain_accuracy`) — fraction of queries
   where the reader's abstain flag equals the gold abstain expectation.
4. **Cross-principal leakage** — count of retrieved items not readable by
   the requester principal. Required zero.
5. **Deletion persistence** — count of deleted-event evidence retrieved
   after the delete lifecycle action. Required zero. Providers whose
   upstream cannot delete record the capability as `unsupported` (OptMem);
   the finding is reported, not simulated.
6. **Export round-trip fidelity** — retrieval parity between pre-export and
   post-import states, verified on DEV (parity >= 0.98 required) and
   recorded as the capability outcome on TEST.

Cost and latency are **co-primary operational metrics**: reported as
distributions per run from the ledger and traces. They are never
tie-breakers invented after the data exists.

## 9. Categories and sample sizes

The 17 query kinds (DEV and each TEST pack): `current_state`,
`historical`, `supersession`, `changed_preference`, `temporary_validity`,
`expiry`, `abstention`, `multi_hop`, `authority_conflict`, `provenance`,
`cross_user`, `role_group`, `deletion`, `do_not_store`, `poisoning`,
`recovery`, `migration`.

- DEV: 80 queries across the 17 kinds (per-kind counts in the dataset card).
- TEST: 192 queries total (3 packs x 64), balanced per pack.
- Repeats: 3 per query -> 576 reader requests per provider run, 576 per
  control run.
- Per-kind diagnostics are reported for every primary outcome where the
  kind is applicable.

## 10. Practical thresholds (preregistered)

- Oracle control on TEST: gold recall@5 = 1.0 and reader accuracy >= 0.95;
  failure means the reader protocol or harness is broken and the run set is
  invalid, not a provider result.
- No-memory control: abstain accuracy = 1.0.
- Random-retrieval: recall@5 within [0.0, 0.25] (chance band).
- Leakage outcomes: 0 for cross-principal and deleted evidence across all
  providers; any nonzero count is reported as a measured failure, never
  rescored or filtered.
- Export parity: >= 0.98 on DEV.
- Statistical claim: Holm-adjusted p < 0.05 AND 95% block-bootstrap CI
  excluding 0 AND >= 5 discordant pairs (McNemar) AND absolute difference
  >= 0.05 on the primary outcome.

## 11. Exclusions and failure policy (preregistered)

- There are no post-hoc exclusions. Every planned attempt is executed or
  reported as not-run with the recorded reason.
- Failed attempts stay in the denominator: timeouts, errors, unsupported
  capabilities, invalid JSON, and retries are counted.
- A required preflight failure -> `aborted_preflight`; dataset failure ->
  `invalid_dataset`; restore mismatch or retrieval mutation ->
  `invalid_invariant`; each aborts only the affected run and preserves all
  evidence.
- Reader retries are capped at 2; a failed request is one failed attempt.
- Hindsight admission is conditional on the Phase 1 environment gate and
  live API verification. If the gate cannot be met, Hindsight is reported
  as not-run (deferred), not scored as zero.
- OptMem's append-only upstream makes deletion-persistence
  `unsupported`; its other outcomes are scored normally. If its lifecycle
  run invalidates (as on DEV), the run is reported as `invalid_invariant`
  with the evidence preserved.
- Nondeterminism: repeats are frozen at 3 because the pilot found no
  material divergence. Any material divergence across repeats on a scored
  run flags that run; divergences are reported, never silently averaged.

## 12. Statistical analysis

- Blocks are storylines (subject), matching correlated queries.
- Paired differences per metric, block bootstrap with 10,000 resamples,
  seed 20260805, 95% CI.
- Exact two-sided McNemar on discordant query pairs per metric.
- Holm-Bonferroni correction within each declared metric family.
- Reliability: pass@1 and all-success rate over the 3 attempts.
- Failure rates: reader error attempts, invalid runs, aborted runs.
- Operational: latency and cost distributions per run.

Full procedure: `protocols/v1/analysis-plan.md`.

## 13. Cost ceiling

- Pricing (verified 2026-08-06, time-sensitive, re-verify before runs):
  input $0.14 / 1M tokens, output $0.28 / 1M tokens.
- Expected Phase 1 reader cost from pilot actuals: about USD 0.08
  (576 requests x 3 repeats on TEST; pilot per-request averages ~540 input /
  ~241 output tokens). Budget-saturating worst case about USD 0.54.
- Hard ceilings, enforced fail-closed by the gateway proxy: USD 1.00 per
  provider run, USD 10.00 global.
- The controlled track makes no provider-native model calls (GBrain
  no-embedding, Mem0 infer=False, OptMem none, Hindsight LLM features off);
  any future gateway-routed provider call is inside the same ceilings and
  ledgered.
- No paid request occurs without user approval of the stated maximum.

## 14. Dry run requirement

Before any scored run, `scripts/freeze_protocol.py --dry-run` must pass with
zero manual intervention: it verifies the committed freeze and runs the $0
offline plumbing suite on DEV (offline stub reader).

## 15. Freeze, versioning, and invalidation

- `protocols/v1/config-freeze.json` (generated by
  `scripts/freeze_protocol.py`) hashes the code commit, lock files, provider
  images, configs, schemas, DEV corpus, reader prompt, scorer modules,
  protocol documents, and the unopened TEST commitment.
- The local tag `protocol-v1-freeze` marks this state. It is never pushed
  without user approval.
- After the freeze, any change to code, configs, datasets, the prompt, the
  scorer, or provider pins creates a new benchmark version
  (`protocol-v2`) and invalidates the unopened or partially opened run.

## 16. Publication rules

- Public artifacts are released only after results are frozen and
  reproduction metadata is complete; no push or publication without user
  approval.
- Provider licenses are respected: OptMem (no license) is never vendored or
  redistributed; results and harness code are the deliverables.
- Reports state limitations, unresolved differences, and provider-specific
  operational characteristics. No winner narrative precedes the frozen
  tables.
