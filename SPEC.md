# Memory Sovereignty Benchmark - working spec (Phase 0)

The canonical, complete plan is the Notion page
[Memory Sovereignty Benchmark - Final Research & Execution Plan](https://app.notion.com/p/3b4916c73ada81f8b196e8952eed8554).
This file is the repo-local, condensed working reference and the definition of
Phase 0 scope. Where they differ, the Notion page wins.

## Thesis

As model intelligence becomes cheap and interchangeable, durable advantage
moves to evaluation, architecture, allocation, and **ownership of state**.
Switching models may become trivial; switching years of accumulated memory may
not. "Own the context, not the conversation."

## Research question

> Can an AI memory system maintain correct, authorized, erasable, evolving,
> useful, user-owned state under controlled conditions - and can that state
> survive the loss or replacement of the memory provider itself?

## Method (abridged)

Four observable stages, so every failure is attributable:

1. Ingestion/consolidation - did the provider turn source history into the right
   memory state?
2. Retrieval - did it return correct evidence for the query?
3. Reader - the frozen, attested reader receives only fixed prompt + normalized
   evidence + question (stateless, no history).
4. Scoring - private deterministic scorer against structured ground truth.

Diagnosis: bad state -> ingestion failure; good state/bad recall -> retrieval
failure; good recall/bad answer -> reader-model failure; all good -> success.

Tracks (never combined into one leaderboard score):

- Track A - Controlled: same reader model, events, queries, clock, prompt,
  context budget, evaluation logic across providers.
- Track B - Product-native: each provider configured as intended.

## Model policy

- Planned primary intelligent component: official `deepseek-v4-flash`
  (expected dated release DeepSeek-V4-Flash-0731). Record requested and returned
  identity; an unverified “Plus” UI label is not a reproducible model name.
- Development may use the OpenGo/OpenCode workflow; the final reproducibility
  sample must use the official DeepSeek API directly.
- No weak local generative model as baseline (model confound).
- Local embeddings allowed where a provider requires them and a CPU model is
  reasonable.
- Avoid LLM judges; prefer deterministic truth. If an LLM judge is unavoidable,
  publish judge model + prompt and manually audit disagreements.

## Contamination threat model (abridged; see Notion section 15)

Channels: cross-provider, query mutation, future-information leakage, public
benchmark contamination, gold-answer leakage, authority collapse, provenance
laundering, cross-user/tenant leakage, deletion leakage, poisoning, self-
generated feedback loops, temporal contamination, async-indexing bias, cache
contamination, context-window cheating, reader cross-request contamination,
judge variance, benchmark tuning, version drift, retry/cost contamination.

Preflight gate: no scoring run starts unless no-memory, oracle, canary
isolation, cross-user isolation, future-leak, gold-inaccessibility, query
read-only/snapshot isolation, network-egress block, fresh-state, and stateless-
reader checks all pass. Any failure -> abort and record the isolation failure.

## Baselines and controls (Phase 0 scope)

- No-memory: reader receives only the question; synthetic fact queries must
  return UNKNOWN (abstain).
- Oracle: reader receives exact gold evidence; proves the case is answerable.
- BM25 / SQLite FTS: how far simple retrieval gets before complex memory
  machinery is justified.
- Full-context: later, where corpus is small enough.

## Query run protocol (Phase 0 implementation)

1. Restore provider from frozen baseline checkpoint.
2. Verify expected store/snapshot hash or state marker.
3. Set deterministic benchmark time.
4. Execute retrieval for the requested principal/scope.
5. Record raw retrieval output + ids + scores + latency.
6. Verify retrieval did not unexpectedly mutate memory.
7. Normalize evidence into provider-neutral reader format.
8. Enforce fixed reader-context token budget.
9. Send one stateless reader request (offline plumbing stub in Phase 0;
   attested official DeepSeek only after the cost-gated pilot).
10. Require structured output.
11. Score against private structured ground truth.
12. Save full run manifest and measurements.
13. Destroy query environment / discard clone.

## Corpus strategy

- DEV split: public in-repo, synthetic, deterministic seed. ~100-150 events,
  40-60 queries in the committed dev set. Used to build adapters and verify the
  harness; the harness tests use a smaller slice.
- Hidden TEST split: generated/frozen only after design stabilizes; not used for
  provider tuning; never mounted into providers; released only after results
  are frozen.
- External datasets (e.g., LongMemEval subsets) are secondary compatibility
  tests, not primary evidence.

## Run manifest (abridged; see Notion section 26)

run_id, track, reader provider/model/mode/response model id, memory provider
name/version/commit/image digest, corpus version + sha256 + split, reader
prompt version + sha256, runtime python + lock hash + os, plus provider config,
raw retrieval traces, token counts, retries, timestamps, scorer version, logs.

## Phase 0 acceptance criteria

- `python -m unittest discover -s tests -v` passes.
- `scripts/run_phase0.py` produces runs/ artifacts for no-memory, oracle, and
  BM25 with valid manifests and scores, at effectively $0 API cost.
- Applicable in-process checks pass and static Docker policy renders. Runtime
  egress and semantic-reader checks are not applicable, so Phase 0 is not
  publication-eligible.
- No memory systems installed; no gold in provider state; deterministic clock;
  query-mutation detection active.

## Roadmap

Detailed execution source:
[remaining phases plan](docs/superpowers/plans/2026-08-05-memory-sovereignty-remaining-phases.md).

Phase 1: BM25 + OptMem + GBrain + Mem0 + Hindsight on the personal corpus
(static/evolving recall, current vs historical, abstention, query isolation,
provenance/authority, deletion, catastrophic recovery). Phases 2-7 per the
canonical plan (specialists, continual/dreaming, security/governance,
sovereignty, scale, real-agent usefulness).

Decision rule: recommend -> contribute upstream -> build only if necessary.
Building nothing is a successful outcome.
