# GBrain Native Track Completion Attempt - Supplementary DEV Evidence (v2)

**Status:** `POST-FREEZE SUPPLEMENTARY GBRAIN-NATIVE LOCAL-EMBEDDING RUNS (v2)`
**Date:** 2026-08-08
**Frozen V1 baseline:** Task 15 report commit `c3007f4`; frozen protocol and
results were not modified.
**Prior record:** `docs/reports/gbrain-native-local-supplement.md` documents
the first rejected DEV attempt (snowflake-arctic-embed:335m).

## Outcome

The GBrain native track cannot be completed under the preregistered DEV
guardrail with local embeddings. Two further local embedding models were
evaluated on the same public DEV split with the pinned GBrain
(`15b9863d...`, v0.42.73.2), the same optimized preflight, and the same
`deepseek-v4-flash` reader through the ledgered gateway. Both passed
preflight and retrieved semantically, but both fell below the predeclared
Recall@5 acceptance threshold of 0.85. Per the predeclared rule ("if the
configuration is correct but local embedding performance remains below 0.85:
stop and report"), hidden TEST was **not** run and no further model swaps
were performed.

## Configurations attested and run on DEV

| Attempt | Embedding model | Params | Context | Dims | DEV Recall@5 |
|---|---:|---:|---:|---:|---:|
| 1 (frozen record) | snowflake-arctic-embed:335m | 334M | 512 | 1024 | 0.7639 |
| 2 (this pass) | snowflake-arctic-embed2:latest | 566M | 8192 | 1024 | 0.8194 |
| 3 (this pass) | bge-m3 | ~570M | 8192 | 1024 | 0.8056 |

All three models are embedding-only, fully local via Ollama 0.32.6 at
`http://127.0.0.1:4713`. bge-m3 is one of the models asserted by the pinned
GBrain Ollama recipe; arctic-embed2 is the higher-quality successor of the
initially used variant. No hosted embedding provider, no Gemini call, and no
GBrain upgrade were used.

## DEV results (attempts 2 and 3, this pass)

| Metric | arctic-embed2 | bge-m3 |
|---|---:|---:|
| attempts | 80 | 80 |
| recall@1 | 0.4444 | 0.4306 |
| recall@5 | 0.8194 | 0.8056 |
| recall@10 | 0.8333 | 0.8194 |
| gold_evidence_recall@5 | 0.8125 | 0.7986 |
| evidence_id_precision | 0.6875 | 0.6896 |
| evidence_id_recall | 0.8194 | 0.8194 |
| forbidden_evidence_total | 32 | 42 |
| cross_principal_evidence_total | 0 | 0 |
| deleted_evidence_total | 0 | 0 |
| reader_accuracy | 0.825 | 0.825 |
| abstain_accuracy | 0.95 | 0.95 |

Frozen V1 comparison: controlled GBrain (keyword, no embeddings) DEV
Recall@1 = 0.618, Recall@5 = 0.982. The embedding-backed native search is
operational but ranks the distinctive-token corpus worse than the product's
own keyword path.

## Preflight

Both runs passed all 11 required checks (network/egress policy,
gold-inaccessibility, no-memory control, oracle control, fresh state, canary
isolation, cross-user isolation, future leakage, query mutation,
reader statelessness, compose policy). Zero leakage, zero mutation.

## Interpretation

- The failure is not specific to one embedding model: three models across
  two families and three context lengths converge on the 0.76-0.82 band.
- The retrieval surface (adapter `search` per-term union over the pinned CLI)
  is identical to the controlled configuration that reaches 0.982; enabling
  embeddings changes GBrain's ranking, not the adapter.
- This does not establish that GBrain, Ollama, or any embedding model is
  inadequate generally; it establishes that this pinned GBrain +
  local-embedding configuration does not meet the predeclared acceptance
  rule on this corpus.
- A hosted embedding fallback (for example Gemini) would require a new
  explicit instruction per the standing policy and was not used.

## Cost (this pass)

Attempts 2 and 3, ledgered through the benchmark gateway: 170 requests,
353,131 input tokens, 62,650 output tokens, USD 0.06698 at the recorded
pricing. No hidden TEST API calls were made.

## Machine-readable evidence

`runs/followups/gbrain-native-local/` (gitignored):

- `dev-attempt-20260808T014248Z/` - arctic-embed2 attempt
- `dev-attempt-20260808T020144Z/` - bge-m3 attempt
- `environment-attestation.json` - final attestation (bge-m3)

## Final GBrain native status

**No hidden TEST supplementary GBrain-native local-embedding result exists.**
The correct status remains: technically supported by the pinned version,
DEV-validated as operational with three local embedding configurations, all
rejected by the preregistered Recall@5 guardrail (best DEV Recall@5 =
0.8194), and stopped without a hosted-embedding fallback.
