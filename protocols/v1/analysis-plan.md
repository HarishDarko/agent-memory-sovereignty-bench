# Analysis Plan — Protocol v1, Personal Controlled Track

**Status:** FROZEN together with `personal-controlled.md` under tag
`protocol-v1-freeze`. This plan defines how the frozen data is turned into
tables and claims. Analysis code is deterministic; the same inputs always
produce the same report.

## 1. Principles

1. The data decides. No preference for or against any system exists before
   the frozen run data is analyzed.
2. Tables first, conclusions second. Public output begins with the metric
   matrix and diagnostics; prose conclusions are written from those tables.
3. Every claim is labeled: `resolved`, `unresolved`, `unsupported`, or
   `invalid`, per the decision rules in section 5. No claim is made from a
   single run or from an invalidated run.
4. No winner announcement. Comparisons are statements about measured
   differences with uncertainty, not verdicts about systems.
5. Blinding: initial QA runs on blinded provider IDs so that no analyst
   (human or model) can steer checks by knowing which provider produced
   which numbers.

## 2. Inputs

- Run manifests, retrieval traces, scores, gateway logs, and the ledger
  under `runs/protocol-v1/` (one directory per provider/control).
- The frozen freeze record `protocols/v1/config-freeze.json`.
- The hidden TEST commitments (`datasets/commitments/test-v1.json`) as the
  integrity anchor; gold is read only by the scorer at scoring time and is
  never printed into reports.

## 3. Blinding protocol

1. Before analysis, provider IDs are mapped to opaque labels P1..Pn via a
   deterministic, committed mapping file (created at analysis time, kept
   out of the report).
2. QA checks (section 6) run on blinded tables. Any anomaly is investigated
   without revealing provider identity.
3. After QA sign-off, the mapping is revealed and the final report is
   assembled. Blinding never changes numbers; it only changes when names
   appear.
4. Controls are not blinded (no-memory, oracle, random, baselines) because
   their roles are preregistered and their expected behaviors are fixed.

## 4. Outputs

### 4.1 Metric matrix

Rows: every participant (controls and providers). Columns: the declared
metric families from `benchmark/metrics.py`:

- retrieval: `gold_evidence_recall@5`, `chain_complete@5`,
  `evidence_id_precision`, `evidence_id_recall`,
  `forbidden_evidence_total`, `cross_principal_evidence_total`,
  `deleted_evidence_total`;
- reader: `reader_accuracy`, `abstain_accuracy`, `authority_correct`;
- reliability: `pass_at_1`, `all_success_rate`;
- operational: `mean_latency_ms`, `mean_tokens`.

Primary-outcome columns (from `personal-controlled.md` section 8) are
highlighted: complete-chain@5, typed answer correctness, calibrated
abstention, cross-principal leakage, deletion persistence, export round-trip
fidelity. Cost and latency are co-primary operational columns, reported as
distributions (min/median/max, mean, per-request cost from the ledger).

### 4.2 Paired comparisons

For every pair of participants on every primary metric:

- observed mean difference;
- 95% block bootstrap CI (10,000 resamples, seed 20260805, blocks =
  subject/storyline);
- exact McNemar p-value on discordant query pairs (binary outcomes only);
- Holm-adjusted p-values within the metric family;
- comparison label (resolved/unresolved/unsupported/invalid) per section 5.

### 4.3 Reliability and failure analysis

- pass@1 and all-success rate over the 3 frozen repeats;
- reader error attempt count and rate (retries, invalid JSON, timeouts);
- invalid/aborted run inventory with status reasons, preserved as evidence;
- failure denominators reported with every rate.

### 4.4 Category diagnostics

For each of the 17 query kinds (and the aggregated category groups in the
dataset card): recall@5, chain-complete@5, reader accuracy, abstain
accuracy, authority correctness, and leakage counts, where applicable.
Category tables are per-participant; no cross-track merging.

### 4.5 Operational distributions

- cost per run (USD, from the ledger and gateway policy pricing) and per
  query;
- latency per query (ms) and per request;
- tokens per request (input/output), evidence truncation rate
  (`omitted_items` in traces).

## 5. Comparison decision rules (preregistered)

A pair comparison on a primary metric is labeled:

- **resolved** — statistical significance (Holm-adjusted p < 0.05 within
  the family) AND the bootstrap CI excludes 0 AND >= 5 discordant pairs
  (for binary metrics) AND the absolute difference >= 0.05 (practical
  threshold). The direction is the sign of the observed difference.
- **unresolved** — data exists but the thresholds above are not met; the
  report says the evidence does not support a claim either way.
- **unsupported** — the capability outcome is `unsupported` or
  `not_applicable` (e.g., OptMem deletion persistence); no comparison is
  made, the finding is recorded.
- **invalid** — the run was invalidated (`aborted_preflight`,
  `invalid_dataset`, `invalid_invariant`) or the participant did not run
  (e.g., Hindsight if the admission gate failed); evidence is preserved and
  the reason is stated.

Leakage metrics (cross-principal, deleted evidence) are reported as counts
with required zero; a nonzero count is a measured failure for that
participant and is never "fixed" by analysis.

## 6. QA checklist (blinded)

1. All planned attempts present: per-participant attempt counts equal the
   preregistered 576 requests (192 queries x 3 repeats) for every executed
   run.
2. All exclusions are preregistered ones from `personal-controlled.md`
   section 11; anything else is a protocol violation, not an exclusion.
3. Oracle control within bounds (recall@5 = 1.0, reader accuracy >= 0.95)
   and no-memory abstention = 1.0; failure invalidates the run set.
4. Random control inside the chance band [0.0, 0.25].
5. Freeze verification passes (`scripts/freeze_protocol.py --verify`).
6. Commitment verification passes for all TEST packs.
7. Trace-level spot checks: evidence IDs cited by the reader exist in the
   sent bundle; no gold path appears in any manifest, log, or trace.
8. Determinism: rerunning the analysis script produces byte-identical
   tables for identical inputs.

## 7. Report structure

1. Summary of the frozen protocol and environment (versions, pins, dates).
2. Metric matrix (primary outcomes first, then families).
3. Paired comparison tables with CIs and adjusted p-values.
4. Reliability, failure, and operational distributions.
5. Category diagnostics.
6. Conclusions written strictly from the tables above, each claim citing
   its table and labeled per section 5.
7. Limitations: corpus size and synthetic nature, single reader model,
   rolling-alias attestation, DEV-selected configurations, provider
   operational characteristics, and anything unresolved.
8. Reproduction manifest: commit, freeze hash, images, commands, seeds,
   ledger summaries (redacted), and environment notes.

## 8. Publication checklist

- Results frozen: reports emitted, hashes recorded, no further scoring runs
  without a new protocol version.
- Redaction pass: no keys, no raw reader content, no gold, no private
  personal data in any public artifact.
- License review: harness and reports are the deliverables; OptMem's
  no-license script is never redistributed; all provider pins and licenses
  are listed.
- Explicit user approval before any push, publish, or external share.
