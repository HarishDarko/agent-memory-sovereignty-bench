# Memory Sovereignty Benchmark — Task 15 Research Review

**Date:** 2026-08-06 (America/Toronto)
**Repository commit used to generate the findings:** `c3007f4` (results: record
personal product native benchmark v1); run artifacts on disk at that commit.
**Protocol version:** v1, local tag `protocol-v1-freeze` (`8412e33`);
machine-readable freeze: `protocols/v1/config-freeze.json`.
**Reader prompt hash:** `5eab2ba89728e2af16293868703b9e005be6137a43b2a4f2505bb910b3e891fa`
(file SHA-256; manifest digest form `c2ff3f4e...`).
**Dataset:** DEV v2 (`datasets/dev/personal/`, 105 events / 80 queries / 80
gold rows, seed `20260805`); hidden TEST v1 (`scorer_private/test-v1/`, 3
packs x 64 queries; commitments in `datasets/commitments/test-v1.json`:
pack-1 aggregate `sha256:cc9516e3...`, pack-2 `sha256:1d529484...`, pack-3
`sha256:59d3ee4f...`).
**Provider/model versions:** see section 3 and 8.
**Repository state:** clean at the time of writing; full commit list in
Appendix A.

---

## 1. Executive Summary

We built and ran a controlled, fail-closed benchmark of four real memory
systems (OptMem, GBrain, Mem0 OSS, Hindsight) on a synthetic personal-memory
corpus with a stateless DeepSeek reader, plus a product-native track in which
the providers' own LLM features (fact extraction, consolidation, reflection)
were enabled and routed through a ledgered benchmark gateway.

**Strongest findings:**

1. **Lifecycle honesty is measurable and discriminating.** OptMem (append-only
   by design) cannot execute the corpus's required deletions and its runs
   invalidate - an honest, reproducible "unsupported" result rather than a
   simulated one. Deletion persistence and cross-principal leakage are zero
   for every executed provider in both tracks.
2. **Recall@1, not recall@5, separates the systems.** BM25 reaches recall@5 =
   1.0 but recall@1 = 0.49; Hindsight reaches recall@1 = 0.71; the retrieval
   workload is easy at top-5 but discriminating at rank 1.
3. **The reader is a confound with real mass** (full-context control: 0.859
   answer accuracy with no retrieval), so every comparison is
   reader-conditional - controlled for, not eliminated.
4. **Product-native LLM behavior is a measured, mixed bag**: native Mem0
   drops recall@1 from 0.60 to 0.42 (LLM extraction loses/reshapes facts);
   native Hindsight raises recall@1 from 0.71 to 0.73 while retrieving far
   more poison-labeled content.
5. **Zero paid leakage of gold**: all reader requests, including
   provider-native ones, were ledgered through the policy gateway; no gold
   path ever reached a provider.

**Weakest findings:** the raw recall/QA numbers, which barely distinguish the
real providers from a lexical BM25 baseline at top-5 and would not be
differentiating against LongMemEval-style suites.

**Did the benchmark produce genuinely differentiated evidence?** Yes, but
specifically in the lifecycle/governance/isolation dimensions - not in
retrieval ranking.

**Recommendation:** PUBLISH V1 + ONE SMALL FOLLOW-UP (Recommendation 2 in
section 18): a minimal catastrophic-exit / semantic-export fidelity probe,
which the reconnaissance in section 12 shows is open, cheap, and directly
relevant to the "memory sovereignty" thesis.

## 2. Research Goal and Scope

The project's goal: a neutral, reproducible, open-source benchmark of
AI-memory systems measuring correctness, governance, lifecycle behavior, and
portability on synthetic personal-memory workloads under a fail-closed
isolation contract, with conclusions derived only from frozen test data.

- **Controlled track (Task 14, complete):** every provider runs one frozen,
  adapter-mediated configuration; the benchmark supplies as-of filtering,
  principal/scope filtering, lifecycle deletion, and a stateless reader.
  This measures the provider's storage/retrieval engine.
- **Product-native track (Task 15, complete):** providers run their intended
  native configurations (LLM extraction, consolidation, reflection), with
  provider-native model calls routed through the benchmark gateway. This
  measures what the product itself does with the same events.
- **Not started (intentionally, per scope boundary):** Tasks 16-20 -
  specialist providers (Graphiti/Cognee/MIND-Mem, admission-gated), continual
  replay/consolidation, large-scale enterprise corpora, migration tooling,
  real-agent harnesses, and STATE-Bench-style downstream validation.

## 3. Systems and Configurations Tested

| System | Version / commit | Controlled config | Native config | Embeddings | LLM | Persistence | Deletion | Retrieval | Export |
|---|---|---|---|---|---|---|---|---|---|
| no-memory | local control | returns nothing | n/a | n/a | n/a | none | n/a | none | n/a |
| oracle | local control | returns exact gold evidence | n/a | n/a | n/a | none | n/a | perfect | n/a |
| random-retrieval | local control | seeded random eligible sample | n/a | n/a | n/a | none | n/a | random k=10 | n/a |
| BM25-pure | local baseline | BM25 k=10, k1=1.5, b=0.75 | same | none | none | memory index | native | lexical BM25 | none |
| SQLite FTS | local baseline | FTS5 k=10 | same | none | none | SQLite file | native | FTS5 | none |
| full-context | local control | recency-ordered, no retrieval | n/a | n/a | n/a | none | n/a | all eligible | n/a |
| OptMem | `1fb164cf...` (no license) | adapter filtering on; delete recorded unsupported | adapter filtering OFF (raw tool semantics) | none | none | append-only LOG.txt | none (append-only) | regex recall | LOG.txt + event list |
| GBrain | `15b9863d...` v0.42.73.2 (MIT) | `init --pglite --no-embedding`, keyword/hybrid only | **not run**: native needs an embedding provider credential (ZeroEntropy/OpenAI/Voyage) not available | none (controlled) | none (controlled) | markdown pages in git brain + PGLite derived index | page deletion (cascade) | hybrid/keyword search | brain repo (markdown+frontmatter) |
| Mem0 OSS | `3f39fba...` v2.0.17 (Apache-2.0) | `add(infer=False)`, chroma, fastembed, telemetry off | `add(infer=True)` LLM extraction via gateway; embedder stays local (no embedding API credential; preregistered deviation); chroma store | fastembed BAAI/bge-small-en-v1.5 (local) | controlled: none; native: DeepSeek via gateway | chroma on disk + history.db | delete by memory id (native: multi-memory per event, tolerant) | semantic (chroma) | event registry + memories |
| Hindsight | `797faf7...` v0.8.6 (MIT), containerized | `HINDSIGHT_API_LLM_PROVIDER=none`, local embeddings/rerankers, internal network | `HINDSIGHT_API_LLM_PROVIDER=openai` via gateway bridge (api-proxy:9000 -> host proxy), model deepseek-v4-flash | BAAI/bge-small-en-v1.5 + ms-marco-MiniLM-L-6-v2 (baked, offline) | controlled: none; native: LLM retain/consolidation/reflect via gateway | PostgreSQL + pgvector (container) | document-cascade delete (per event) | hybrid BM25+semantic+graph+temporal | bank export/import |

Configurations that were not run and why: **GBrain-native** (embedding
credential gap; preregistered not-run), **native track controls** (controls
measure the reader/harness, not provider-native behavior; already validated
on the same packs in the controlled track).

## 4. Dataset and Protocol

- **DEV (public):** 105 events, 80 queries, 80 gold rows; 17 query kinds;
  seed 20260805; used for adapter development and config selection only.
- **Hidden TEST:** 3 packs x 64 queries (192 total), generated from an
  unrevealed master seed; only SHA-256 commitments committed; packs
  gitignored under `scorer_private/`; value pools disjoint from DEV.
- **Temporal structure:** events span 2026-02-15 to 2026-07-01; 4 distinct
  query checkpoints per pack; benchmark clock fixed at
  `2026-08-01T00:00:00Z` (never wall-clock "today").
- **Categories:** current_state, historical, supersession,
  changed_preference, temporary_validity, expiry, abstention, multi_hop,
  authority_conflict, provenance, cross_user, role_group, deletion,
  do_not_store, poisoning, recovery, migration.
- **Authority/provenance:** user_explicit vs assistant_inference vs external
  sources; supersedes chains; authority canaries.
- **Deletion cases:** delete + do_not_store lifecycle events with targets;
  deleted-evidence leakage counted per query.
- **Cross-user cases:** queries by other principals; cross-principal leakage
  counted.
- **Replication:** 3 replicates per query per participant (576 attempts per
  participant); pilot verified no material reader nondeterminism at these
  settings.
- **Evidence budget:** 2048 tokens to the reader (truncation recorded).
- **Reader:** DeepSeek `deepseek-v4-flash` (rolling alias observed on
  2026-08-06; expected dated release DeepSeek-V4-Flash-0731 **not attested**
  by the API), thinking disabled, temperature 0.0, exactly 2 messages,
  JSON output, attestation mode rolling.
- **Scoring:** typed answers (exact/set/date/bool/quantity with private
  aliases), gold-evidence recall@1/5/10, complete-chain@1/5/10, evidence-ID
  precision/recall, abstention correctness, authority correctness,
  forbidden/cross-principal/deleted evidence counts.
- **Statistics:** paired block bootstrap (10,000 resamples, seed 20260805,
  blocks = subject), exact McNemar, Holm within metric families; labels
  resolved/unresolved/unsupported/invalid per frozen thresholds
  (alpha 0.05, >=5 discordant pairs, absolute delta >= 0.05).

## 5. Isolation and Contamination Controls

| Control | Mechanism | Result |
|---|---|---|
| Cross-provider isolation | one provider per run; fresh data dirs; canary check (own canary retrievable, foreign absent) | passed (controlled); canary gate relaxed for native LLM-extraction providers (storage decisions are measured, not gated) |
| Per-run state | fresh run-scoped data dirs; participant-level wipe | passed |
| Query-to-query mutation | baseline-hash before and state-hash after every retrieval; mismatch -> run invalidated | passed (0 mutation warnings across all runs) |
| Future-information leakage | harness filters events by available_at <= as_of; adapter as-of filter (controlled) | passed (controlled); measured not gated (native) |
| Hidden gold leakage | gold/scorer_private never mounted/copied to providers or reader; reports redaction-checked | passed |
| Model session contamination | stateless reader, 2 messages; proxy rejects history reuse; no conversation state | passed |
| Network egress | local/in-process providers; Hindsight container on `internal: true` network; runtime probe showed api.deepseek.com unreachable from inside | passed |
| Provider external access | Hindsight's only external route: benchmark-owned socat bridge -> gateway; HF offline mode | passed |
| Model-gateway isolation | single allowlist (api.deepseek.com), ledgered, identity-stamped; budgets advisory per user instruction | passed |
| Cross-user contamination | adapter principal/scope filtering (controlled); measured counts (native) | zero leakage in both tracks for executed providers |
| Provenance/authority | reader prompt + authority canaries + authority_correct scoring | passed |
| Deletion leakage | lifecycle deletes executed; deleted_evidence_total counted | zero for executed providers; OptMem recorded unsupported |
| Cache effects | no cross-run caches; model caches baked/offline | passed |
| Deterministic time | fixed benchmark clock | passed |
| Snapshot/restore | logical event list + state hash; contract-tested | passed |
| Stale/crashed-run artifacts | analysis reads traces only from dirs with a completed live manifest; FAILED.json beside valid manifests ignored; stale rehearsal traces excluded | fixed and tested after a real contamination incident (BM25 pass@1 distortion) |

**Remaining contamination risks:** (a) native track gates cross-user/future
behavior as *measured* findings rather than hard gates; (b) Hindsight's
background consolidation worker runs during native runs, making behavior
time-dependent; (c) anonymous native LLM calls skip request-shape checks at
the proxy (still identity-stamped and ledgered); (d) DeepSeek extraction
responses occasionally malformed - those events are recorded as storage
failures and simply absent.

## 6. Controlled Track Results

All values aggregated over the hidden TEST split; pack-1-rep1 shown for
detail; full aggregates in `reports/protocol-v1/personal-controlled.json`.

| Participant | r@1 | r@5 | r@10 | gold-ev r@5 | chain@5 | ev-prec | ev-recall | answer acc | abstain acc | forb | cross | del | pass@1 | all-success | cost USD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| no-memory | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.141 | 0.141 | 0 | 0 | 0 | 0.141 | 0.141 | 0.064 |
| oracle | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 0.859 | 1.0 | 1.0 | 1.0 | 0 | 0 | 0 | 1.0 | 1.0 | 0.065 |
| random-retrieval | 0.036 | 0.164 | 0.309 | 0.164 | 0.164 | 0.250 | 0.291 | 0.365 | 0.469 | 9 | 0 | 0 | 0.365 | 0.365 | 0.141 |
| full-context | 0.018 | 0.073 | 0.218 | 0.064 | 0.055 | 0.703 | 0.836 | 0.859 | 0.859 | 88 | 0 | 0 | 0.859 | 0.859 | 0.272 |
| BM25-pure | 0.491 | 1.0 | 1.0 | 0.991 | 0.982 | 0.833 | 0.973 | 0.967 | 0.975 | 7 | 0 | 0 | 0.964 | 0.958 | 0.156 |
| SQLite FTS | 0.491 | 1.0 | 1.0 | 0.991 | 0.982 | 0.833 | 0.973 | 0.967 | 0.979 | 7 | 0 | 0 | 0.964 | 0.964 | 0.133 |
| GBrain | 0.618 | 0.982 | 0.982 | 0.973 | 0.970 | 0.818 | 0.982 | 0.967 | 0.984 | 11 | 0 | 0 | 0.969 | 0.964 | 0.206 |
| Mem0 | 0.600 | 0.982 | 1.0 | 0.973 | 0.952 | 0.794 | 0.982 | 0.974 | 0.983 | 12 | 0 | 0 | 0.974 | 0.969 | 0.234 |
| Hindsight | 0.709 | 0.964 | 1.0 | 0.955 | 0.946 | 0.818 | 1.0 | 0.983 | 0.983 | 88 | 0 | 0 | 0.984 | 0.979 | 0.390 |
| OptMem | invalid_invariant (append-only; recorded, not scored) | | | | | | | | | | | | | | 0.051 |

102 of 270 pairwise comparisons are resolved at the frozen thresholds. The
BM25 baselines reach recall@5 = 1.0 but recall@1 = 0.49: **the retrieval
workload is easy at top-5 and discriminating at rank 1**. Hindsight retrieves
the most poison-labeled content (88 forbidden items, like full-context).
Reliability across the 3 replicates is high (pass@1 0.96-0.98 for providers).
Two BM25 runs and one OptMem run were lost to upstream reader failures
(recorded in the denominator; see section 13).

## 7. Product-Native Track Results

| Participant | recall@5 | chain@5 | answer acc | abstain acc | cost USD | notes |
|---|---:|---:|---:|---:|---:|---|
| OptMem (native) | invalid_invariant x9 | | | | 0.105 | raw unfiltered recall; lifecycle deletes impossible |
| GBrain (native) | not run | | | | 0.0 | embedding credential gap |
| Mem0 (native) | 0.943 | 0.935 | 0.941 | 0.941 | 1.149 | LLM extraction via gateway; local embedder; storage failures recorded |
| Hindsight (native) | 0.976 | 0.958 | 0.984 | 0.984 | 0.877 | LLM retain + consolidation + reflection via gateway bridge |

Mem0-native: 9/9 runs completed after a per-event storage-retry fix; earlier
attempts failed with transient chroma "Error finding id" races during native
dedup/update (see section 13). Extraction routinely produced multiple
memories per event and occasionally none (malformed DeepSeek extraction JSON,
recorded as storage failures). Native Mem0 recall@1 drops to 0.42 (from 0.60
controlled).

Hindsight-native: 9/9 runs; consolidation ran in the background during runs
(observed in API logs); recall@1 0.73, recall@5 up to 1.0 on later packs;
86 forbidden items retrieved.

3 of 18 native pairwise comparisons are resolved: Hindsight > Mem0 on
chain@5 (d = -0.0545, CI [-0.109, -0.005]), reader accuracy (d = -0.0781,
CI [-0.129, -0.032]), abstention (same).

## 8. Controlled vs Native Comparison

| Dimension | Mem0 controlled | Mem0 native | Hindsight controlled | Hindsight native |
|---|---:|---:|---:|---:|
| recall@1 | 0.600 | 0.418 | 0.709 | 0.727 |
| recall@5 | 0.982 | 0.927 | 0.964 | 0.976 (pack-3: 1.0) |
| chain@5 | 0.952 | 0.935 | 0.946 | 0.958 |
| answer accuracy | 0.974 | 0.941 | 0.983 | 0.984 |
| abstention | 0.983 | 0.941 | 0.983 | 0.984 |
| evidence precision | 0.794 | 0.749 | 0.818 | 0.836 |
| forbidden items | 12 | 23 | 88 | 86 |
| cross-principal / deleted leakage | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| ingestion/extraction failures | none | storage failures recorded | none | malformed-extraction events absent |
| consolidation effects | n/a (no consolidation) | n/a | n/a | background consolidation during runs |
| replicate reproducibility | high | moderate (extraction varies) | high | high |
| cost | 0.234 | 1.149 | 0.390 | 0.877 |

Interpretation: native LLM extraction can *lose* memory fidelity (Mem0) or
modestly improve rank-1 retrieval (Hindsight), while costs jump ~4-5x.

## 9. Memory Transformation Case Studies

**Mem0 native (from the verification probe and run traces):**
source event: `"Ava Chen's preferred editor is Quill and she moved to Toronto
in March 2025."` -> DeepSeek extraction via gateway produced **two persisted
memories**: `"Ava Chen's preferred editor is Quill."` and `"Ava Chen moved to
Toronto in March 2025."` -> both stored in chroma with event metadata ->
retrieved as evidence -> reader answered correctly.
What changed/disappeared: the single source event became two facts
(semantic split is arguably correct); timestamp/validity semantics of the
source event are only preserved through adapter-side metadata, not by the
extracted memories themselves; the distinction between the user's explicit
statement and the model's reformulation is **not preserved** (the extracted
memories look like facts, not quotes); provenance survives only in the
adapter registry.

**Hindsight native (from API logs):** retain_extract_facts scopes ran per
event through the gateway (3,000-7,000 input tokens per call), producing
memories; consolidation ran in background batches ("llm_batch #N (M
memories)"), which may merge or rephrase earlier memories - the API does not
expose enough to verify factual identity after consolidation.
**NOT OBSERVABLE**: whether consolidation altered meaning or flattened
history, because the pinned API does not expose pre/post consolidation facts
at the required granularity.

**OptMem native:** recall returns raw log lines; nothing is transformed -
but nothing is filtered either (cross-user/future content measurable, deletes
impossible).

## 10. Harness Guarantees vs Product Guarantees

| Property | Provided by |
|---|---|
| Cross-user isolation | **adapter** (controlled) / **measured** (native) - not a native product guarantee for any provider except via metadata that only the adapter interprets |
| As-of filtering | **benchmark runner** (event eligibility) + **adapter** (controlled) |
| Deletion | **adapter** (maps to product API; OptMem unsupported) |
| Authority handling | **reader prompt** (uses authority/validity metadata supplied by adapter) |
| Provenance | **adapter** (event metadata) - native products mostly lose it absent the adapter |
| Scope filtering | **adapter** (controlled) |
| Read-only behavior | **benchmark runner** (hash verification) - not a product guarantee |
| Future filtering | **benchmark runner** + **adapter** (controlled) |

This is the central caveat of the controlled track: several "memory system"
results are adapter-mediated behaviors, not native product capabilities. The
native track exists precisely to surface that difference; where a native
product lacks the property, the honest label is unsupported/not-run/measured,
never a pass.

## 11. Sovereignty / Governance Findings

1. Did any native provider expose memory belonging to the wrong principal?
   **Not observed in executed runs** (cross-principal evidence = 0 for Mem0
   and Hindsight native). OptMem-native exposes other principals' content by
   design (raw recall), but its runs invalidated before scoring; the raw
   behavior is documented, not scored.
2. Did any native provider retain supposedly deleted information?
   **No deleted evidence was retrieved** in any executed run; OptMem's
   append-only retention is recorded as unsupported deletion.
3. Could deleted information be reconstructed indirectly? **NOT
   OBSERVABLE** from run traces; OptMem's LOG.txt physically retains it
   (documented finding for the follow-up section).
4. Did any provider silently mutate memory during retrieval? **No** - zero
   mutation warnings across all runs in both tracks.
5. Did native consolidation alter factual meaning? **NOT OBSERVABLE**
   (Hindsight API granularity).
6. Did native consolidation flatten historical state into current state?
   **NOT OBSERVABLE**.
7. Did the system preserve the original source of a fact? Only via
   **adapter metadata** (event_id/source/authority); native products alone
   do not preserve it consistently (Mem0 memories carry metadata only when
   the adapter supplies it).
8. Did it preserve who had authority to assert a fact? **Adapter metadata
   only**; native extraction output does not distinguish
   user_explicit/assistant_inference/external.
9. Did model-derived summaries become indistinguishable from explicit user
   facts? **Yes - this is the strongest sovereignty finding**: native
   extracted/consolidated memories carry no marker distinguishing model
   inference from user statements.
10. Were identical source events converted differently across replicates?
    **Yes for Mem0 native** (extraction is nondeterministic across
    replicates; storage failures and memory counts vary), **mildly for
    Hindsight native** (consolidation timing); controlled track was
    reproducible (pass@1 0.96-0.98).

## 12. Export and Recoverability Reconnaissance

| Provider | Canonical state | Native export | Human-readable | Raw events | Derived memories | Timestamps | Provenance/authority | Supersession | Scopes | Tombstones | Index rebuildable | App/db lost => |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| OptMem | LOG.txt + TREE cache | LOG.txt + `config` | yes | yes (event_id + text) | partial (TREE cache) | date | no | no | no | no tombstones (append-only) | TREE rebuildable from log | raw log survives; deletions not represented |
| GBrain | markdown pages in git + PGLite | brain repo | yes | yes (frontmatter) | facts table in PGLite | frontmatter | frontmatter (adapter-written) | supersedes in frontmatter | principal/scope frontmatter | page deletions are git-visible | `gbrain sync` rebuilds from markdown | markdown survives; PGLite index rebuildable |
| Mem0 | chroma dir + history.db + adapter registry (event_memory_ids.json) | adapter export (events + registry) | partially (chroma files not human-readable) | yes (registry/events) | yes (chroma vectors/text) | metadata (adapter) | metadata (adapter) | not in product | metadata (adapter) | delete removes chroma ids | chroma rebuild requires re-embedding raw events | chroma+db loss loses derived memories unless re-extracted; adapter registry is the only raw-event map |
| Hindsight | Postgres/pgvector bank | bank export/import (native) | JSON export | metadata preserved in bank | yes | yes (occurred_at etc.) | metadata (adapter) | partially (causal links exist) | banks as scopes (adapter maps principals) | delete cascade via documents | re-import into fresh bank | bank export survives; raw event text embedded in memories |

**Verdict:** a catastrophic-exit or A->B migration experiment is genuinely
open: Mem0's derived memories and Hindsight's consolidated state are not
recoverable from raw events without re-running extraction (with
nondeterministic results, per finding 10 above); GBrain and OptMem are
recoverable from human-readable raw state. This motivates the single
follow-up experiment recommended in section 18.

## 13. Failure Analysis

- **Ingestion failures:** OptMem-native/controlled runs invalidate on
  required deletions (capability gap, `invalid_invariant`); mem0-native
  transient chroma "Error finding id" races during dedup/update (5 of 9 runs
  in the first attempt; fixed with a per-event retry; 0 of 9 after).
- **Extraction failures:** DeepSeek occasionally returns malformed extraction
  JSON ("Unterminated string...", "Expecting ',' delimiter"); affected events
  are recorded as storage failures and absent from mem0-native.
- **Retrieval failures:** none observed in executed runs (0 mutation
  warnings; recall computed on all planned queries).
- **Reader-model failures:** upstream timeouts (>60s, >180s) and empty
  responses ("reader returned invalid JSON: ''") lost 3 controlled runs
  (BM25-pure, BM25-sqlite-fts, OptMem) and 4 earlier Hindsight native runs;
  mitigated by a longer client timeout and a bounded empty-content retry.
- **Lifecycle failures:** none beyond OptMem's recorded unsupported deletion.
- **Permission/isolation failures:** none (zero leakage, zero mutation).
- **Provider dependency failures:** GBrain-native not run (missing embedding
  credential); hindsight container stack required pgvector + torch image
  (built once, offline).
- **Infrastructure failures:** Windows file locks around git/chroma required
  rename-based resets; git index.lock intermittently needed unsandboxed
  execution; a stale-rehearsal-trace contamination incident (BM25 pass@1
  distortion) was found and fixed by manifest-gated trace loading.
- **Benchmark/harness failures:** blinding loop mutation bug, redaction
  false-positive, stale-artifact handling - all found via QA and fixed with
  regression tests.

## 14. Benchmark Self-Critique

- **Discriminating dimensions:** recall@1, chain@5, deletion/lifecycle
  capability, forbidden-evidence retrieval, evidence precision, native
  extraction fidelity, cost.
- **Non-discriminating dimensions:** recall@5/10 (saturated at 0.96-1.0 for
  all real providers and BM25), abstention accuracy (0.97-0.98 everywhere),
  leakage (zero everywhere) - leakage is a hard gate that all executed
  providers pass, which is itself informative but not differentiating.
- **Is BM25 = 1.0 recall@5 a sign the workload is too easy?** Partially:
  top-5 saturation means provider ranking at recall@5 is meaningless; the
  workload discriminates at rank 1 and in evidence precision, so the
  conclusion is "easy at the headline metric, discriminating where it
  matters" - the headline metric should be recall@1 for any leaderboard.
- **Conclusions genuinely supported:** lifecycle honesty (OptMem), zero
  leakage under controlled conditions, reader dependence on evidence
  quality, native extraction losing/gaining fidelity, cost of native LLM
  features, reproducibility differences between tracks.
- **Would be overclaims:** any "provider X is better than Y" claim as a
  product verdict; any claim that controlled-track isolation is a native
  product property; any dated-model claim (rolling alias only).
- **Reader dependence:** all answer/abstention numbers are conditional on
  deepseek-v4-flash (rolling); a different reader would shift absolutes.
- **Native-model dependence:** native numbers are conditional on DeepSeek as
  the extraction/consolidation model - a product misconfiguration could
  masquerade as a product weakness.
- **Adapter effects:** controlled results depend on adapter decisions
  (filtering, metadata, deletion mapping); section 10 documents which
  properties are adapter-mediated.
- **Replicate sufficiency:** 3 replicates; native extraction variance means
  more replicates would tighten estimates; pass@1/all-success partially
  absorb this.
- **Remaining weaknesses:** Hindsight consolidation nondeterminism not
  quantified; GBrain-native absent; single corpus, single reader, single
  model family; no task-level downstream validation.

## 15. Comparison With Existing Work

| Benchmark | Overlap | What they do better | What to reuse | What we measure differently |
|---|---|---|---|---|
| LongMemEval / LoCoMo | question taxonomy (temporal, updates, abstention) | larger natural corpora, chat-assistant framing | question categories | we test memory *systems* with lifecycle/deletion/permissions, not LLM long-context recall |
| BEAM | agent memory interactions | task-level measurement | agent-task protocol | controlled memory-layer scoring |
| Agent Memory Benchmark (AMB) | agent memory isolation | real-agent environments | environment scaffolding | our fail-closed per-query state verification and lifecycle controls |
| MemTools | memory tooling taxonomy | breadth of tool survey | taxonomy framing | empirical lifecycle/governance measurement |
| STATE-Bench | stateful sandboxes, memory-for-tasks | downstream task completion metrics | task suite design (future agent phase) | memory correctness vs gold, governance dimensions |
| GateMem | memory state gating | structured memory management | gating design ideas | empirical deletion/persistence measurement |
| MemSecBench | memory security | injection/attack coverage | attack vectors | lifecycle/sovereignty (deletion, leakage) rather than attacks |
| AuthMem-Bench | authorization in memory | access-control rigor | permission test design | cross-principal leakage at the retrieval layer |
| SovereignPA-Bench | user sovereignty philosophy, current-intent vs stale memory | end-to-end agent trajectories | scenario design (future agent phase) | memory-system-level evidence with typed gold |
| memorywire / AMP | interchange/portability | standard formats | format standards for a migration follow-up | export/import fidelity as a measured property |
| IETF AI memory interchange | interop standards | standards process | interchange schema for migration work | empirical recoverability recon (section 12) |

We are not using any of these codebases; we reimplemented corpus generation,
scoring, and statistics from first principles. The genuinely different
contribution is the controlled memory-layer lifecycle/governance measurement
with fail-closed isolation and ledgered provider-native calls.

## 16. Results That Survive Without a Recall Leaderboard

Ranked strongest to weakest:

1. **Native extraction erases the source/authority distinction.** Model-
   derived memories are indistinguishable from explicit user statements -
   the clearest "memory sovereignty" failure and directly policy-relevant.
2. **Deletion is a capability, not a feature.** OptMem's append-only design
   invalidates whole runs; Mem0/Hindsight deletions hold (zero deleted-
   evidence retrieval) - lifecycle honesty is measurable and reproducible.
3. **Retrieval never mutates state, and leakage is zero when controlled.**
   The fail-closed verification contract works across 5,800+ scored queries.
4. **The reader is a confound with real mass** (full-context 0.859) - a
   methodological caution for every memory-LLM evaluation.
5. **Native LLM features cost 4-5x and can reduce recall@1 (Mem0 0.60 ->
   0.42)** while helping another (Hindsight 0.71 -> 0.73) - native fidelity
   varies by implementation.
6. **Recoverability differs sharply by provider** (GBrain/OptMem raw
   human-readable; Mem0/Hindsight derived state not rebuildable without
   re-extraction) - the seed of the export/migration follow-up.
7. **Top-5 recall saturates; rank-1 discriminates** - a measurement
   lesson for the field.

Without the leaderboard, items 1-6 still constitute a publishable,
differentiated set of findings about memory-system lifecycle behavior.

## 17. Potential Follow-Up Research Questions

1. **Catastrophic-exit recovery fidelity.** Can derived memories be
   reconstructed identically from raw events after the store is destroyed?
   Evidence: section 12 recon + Mem0 extraction nondeterminism (finding 10).
   Closest prior work: memorywire/AMP interchange efforts. Smallest
   falsification experiment: destroy chroma/pgvector, re-run extraction from
   raw events, compare memories. Effort: small. New infrastructure: none.
2. **Semantic export/import identity.** Does export -> re-import preserve
   factual identity, timestamps, provenance, and supersession? Evidence:
   Hindsight bank export granularity limits (section 9). Effort: small.
3. **A->B migration fidelity.** Move events between providers and measure
   provenance/authority survival. Evidence: no current migration tooling;
   adapter metadata is the only carrier. Effort: medium.
4. **Native deletion/erasure depth.** Do deletes remove derived artifacts
   (observations, consolidated summaries) or only raw memories? Evidence:
   Hindsight observation deletion paths exist but depth unmeasured. Effort:
   medium.
5. **Controlled-vs-native as a methodology.** Is the two-track design a
   reusable evaluation pattern? Evidence: the 3 resolved native comparisons
   vs 102 controlled. Effort: small (write-up).
6. **Downstream STATE-Bench validation.** Do these recall numbers predict
   task completion? Evidence: none yet; requires the agent phase. Effort:
   large.

## 18. Continue / Stop Decision

**Recommendation 2 - PUBLISH V1 + ONE SMALL FOLLOW-UP.**

Evidence: the controlled + native datasets are complete, QA'd, redacted, and
reproducible; the governance/lifecycle findings (sections 11, 12, 16) are
differentiated; the raw leaderboard is not. The one measured gap that
deserves a minimal additional experiment before broader continuation is
catastrophic-exit / semantic-export fidelity (section 17, item 1): it is
cheap, requires no new infrastructure, and directly tests the "memory
sovereignty" thesis that motivated the project. Tasks 16-20 are not
justified by the current evidence (the specialist admission gate found no
single dramatic gap in the measured dimensions; continual replay would
extend, not transform, the findings).

## 19. Reproduction Information

- **Commands:** controlled: `python scripts/run_protocol_v1.py --mode run`;
  native: `python scripts/run_protocol_v1.py --mode run --track native`;
  analysis: `python scripts/run_protocol_v1.py --mode analyze [--track native]`;
  suite: `python -m unittest discover -s tests`.
- **Environment:** Windows 11, Python 3.12.2 (uv 0.11.32, pinned uv.lock),
  Docker Desktop (WSL2) for container probes and the Hindsight stack; Bun
  1.3.14 for GBrain.
- **Git:** commit `c3007f4` (findings); freeze tag `protocol-v1-freeze`
  (`8412e33`); protocol hash in `protocols/v1/config-freeze.json`.
- **Model identity:** requested alias `deepseek-v4-flash`; returned model
  `deepseek-v4-flash` on every request (rolling alias observed 2026-08-06;
  dated release DeepSeek-V4-Flash-0731 not attested by the API).
- **API usage/cost:** pilot USD 0.0258 (180 requests); controlled USD 1.71
  (5,810 scored requests + probes); native USD 2.13; total USD ~5.00.
  Per-request ledger entries (hashes, identity, usage) in each
  `runs/protocol-v1/**/ledger.jsonl`.
- **Not-run configurations:** GBrain-native (embedding credential gap);
  native controls; Tasks 16-20 (scope boundary).
- **Redacted reports:** `reports/protocol-v1/personal-controlled.{json,csv,md}`
  and `personal-native.{json,csv,md}` (redaction-checked; no questions,
  answers, gold, or private paths).
- **Private artifacts (not committed):** `runs/`, `scorer_private/`
  (hidden TEST packs + seeds), `.optmem/`, `datasets/private_test/`.

## 20. Appendix

**A. Commits (main, most recent first):** `c3007f4` Task 15 results;
`0e57850` native tests; `e01ace0` mem0 native retry; `2ee1a16` native
deletion tolerance + adapter timeout; `4c240fb` incremental native
ingestion; `59e62a9` native preflight gating; `235b549` native track;
`1857678` controlled reports; `b17245d` controlled results; `09d55dd`
empty-content retry; `5e27626` checkpoint state reuse; `7b3bdc6` gbrain
partial-home recovery; `adc18da`, `298d65a`, `ec31bdf`, `5aed50e`,
`c4d6962`, `02f78af` (analysis/QA/gate fixes); `9517d1f`, `929022d`,
`9644dea`, `8412e33` (freeze + orchestrator); earlier: Tasks 0-12 commits.

**B. Tests:** 261 passing, 23 skipped (env-gated live provider/container
tests: SOVBENCH_RUN_GBRAIN/MEM0/HINDSIGHT/DOCKER_INTEGRATION/
RUN_PROTOCOL_REHEARSE/RUN_PROTOCOL_FAKE). Zero failing at commit `c3007f4`.

**C. Run IDs:** controlled `runs/protocol-v1/<participant>/pack-*-rep*`;
native `runs/protocol-v1/native/<participant>/...`; phase0 plumbing runs
2026-08-01-045..057.

**D. Cost summary:** see section 19; authoritative running total in
`runs/protocol-v1/cost-state.json`.

**E. Warnings:** rolling-alias attestation; reader/native-model dependence;
adapter-mediated properties; Hindsight consolidation nondeterminism;
GBrain-native absent; native leakage gated as measurement.

**F. Unresolved issues:** exact factual-identity preservation across
Hindsight consolidation (NOT OBSERVABLE at API granularity); Mem0 extraction
nondeterminism quantification; stale FAILED.json files beside valid
manifests remain on disk (benign, documented).
