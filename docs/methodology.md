# Methodology

## Tracks

**Controlled track:** the question is "given normalized memory objects and
benchmark-controlled semantics, how does the underlying system store and
retrieve evidence?" Provider-native extraction/consolidation is disabled.

**Native track:** the question is "what does the actual memory product do with
the same events?" Native behavior differs and is preserved.

The tracks are never merged into one score.

## Lifecycle replay

1. Start clean, isolated provider state.
2. Ingest all non-delete source events in one controlled batch.
3. Apply delete/do-not-store events through the provider's native delete API
   via the adapter lifecycle mapping.
4. Freeze one final state hash.
5. Retrieve paired conditions from that same state without mutation.
6. Verify the state hash before and after every query.

## Evaluation dimensions

- retrieval: gold recall@k, complete-chain@k, precision@k, forbidden and
  stale evidence rates
- reader: typed answer correctness, calibrated abstention, evidence-ID
  precision/recall, authority/provenance correctness, invalid-JSON and retry
  rates
- lifecycle: deletion persistence, export coverage, recovery behavior
- governance: future-information leakage, cross-principal leakage, scope
  enforcement, provenance/authority handling

## Statistics

- paired unit: provider, pack, query, replicate
- exact McNemar on first attempt per query
- paired block bootstrap (10,000 resamples, fixed seed), blocks by
  `pack:subject`
- Holm-Bonferroni within declared metric families
- practical effect threshold declared before TEST; never hunt for
  significance
- failed attempts stay in denominators

## Materiality rule

An effect is material only if all of: adjusted p < 0.05 where applicable,
95% bootstrap interval excludes zero, exact McNemar has at least 5 discordant
pairs, and the absolute delta is at least 0.05. For security/governance
counts (unauthorized, future, deleted evidence), a clear nonzero-to-zero
transition may be material despite limited significance power.

## Reader identity

AMSB is reader-provider neutral. The reader is a separate evaluation layer;
memory-provider adapters never depend on the reader, and the reader never
depends on the provider. New experiments may use any compatible reader
implementation or configuration, but results obtained with a different
reader should be treated as a different experimental configuration.

The researched reader uses the official `deepseek-v4-flash` API alias, whose
2026-07-31 dated release is DeepSeek-V4-Flash-0731. Requested and returned
identity are recorded in every manifest. DeepSeek V4 Flash is the frozen
reference reader for the AMSB Protocol v1 model-backed results; exact
reproduction of those runs requires the frozen DeepSeek configuration. The
offline stub makes no API calls.
