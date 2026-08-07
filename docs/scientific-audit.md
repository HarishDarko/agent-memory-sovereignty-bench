# Scientific Audit of the Existing Implementation

This audit documents what the existing implementation actually did. Nothing
was rerun and no frozen result was altered.

## 1. Scope condition

Question: did the assisted scope condition also apply temporal eligibility
filtering?

Answer: **yes.** `benchmark/capability_attribution.py::assisted_filter`
applies three rules to raw retrieval results: `available_at <= as_of`,
`principal == query.principal`, and requested scope equality. The scope
ablation (`D0-native` vs `D1-assisted`) therefore bundles temporal
eligibility with principal/scope filtering. The scope delta reported in
capability attribution v1 includes the temporal-filter contribution.

Consequences for interpretation:

- The D1-assisted condition is more precisely "benchmark eligibility
  assistance" than "scope assistance" alone.
- The temporal ablation isolates the same filter cleanly (C0 vs C1), so the
  temporal effect itself is not confounded.
- The authority/provenance 2x2 cells all use the eligibility-filtered set
  (identical across cells), so metadata/prompt deltas are not affected, but
  those measurements describe reasoning on an already-filtered evidence set.

No results were changed; this is a documented interpretation constraint.

## 2. Authority/provenance item counts

Question: why do assisted cells appear to have different evidence-item counts
despite intended shared retrieval?

Answer: the raw/assisted counts in the retrieval observations compare the
unfiltered product retrieval (`raw_ids`) with the eligibility-filtered set
(`assisted_ids`). For authority and provenance, the reader cells all share
the assisted set; the difference between raw and assisted counts is the
eligibility filter (future-dated, cross-principal, and wrong-scope items),
not serialization or token budgeting. Token budgeting (`format_evidence`,
budget 2048) applies identically to every cell, and the paired grid
validation enforces one reader item signature per query.

Evidence: retrieval observations show 714 to 638 items for authority and
357 to 321 for provenance across 18 and 9 queries, all 27 changed by
assistance; mutation failures were zero.

## 3. Cost ledger

The published ledger reconciles only values recorded in run manifests and
ledgers; nothing is invented. See `reports/COST-LEDGER.md`.

Summary: capability attribution v1 total USD 0.426423 (GBrain 0.178140
including USD 0.000715 of user-interrupted abandoned calls, Mem0 0.178244,
Hindsight 0.070039), plus the reader pilot ledger under
`experiments/reader-pilot/ledger.jsonl` (dry run $0, live usage recorded).
No other paid services were used.
