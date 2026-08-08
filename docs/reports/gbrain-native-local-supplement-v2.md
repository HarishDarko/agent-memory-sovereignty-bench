# GBrain Native Track Completion Attempt - Supplementary DEV Evidence (v2)

**Status:** `POST-FREEZE SUPPLEMENTARY GBRAIN-NATIVE LOCAL-EMBEDDING RUNS (v2)`
**Date:** 2026-08-08
**Frozen V1 baseline:** Task 15 report commit `c3007f4`; frozen protocol and
results were not modified.
**Prior record:** `docs/reports/gbrain-native-local-supplement.md` documents
the first rejected DEV attempt (snowflake-arctic-embed:335m).

## Outcome

**Status: POST-FREEZE SUPPLEMENTARY DEV EVIDENCE.**

**GBrain native status: Native DEV evaluated and rejected by the
preregistered guardrail; hidden TEST not run.**

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

- The failure cannot be attributed to the initially selected embedding model
  alone: all three tested local embedding configurations remained below the
  preregistered DEV threshold (0.76-0.82 band).
- The retrieval surface (adapter `search` per-term union over the pinned CLI)
  is identical to the controlled configuration that reaches 0.982; enabling
  embeddings changes GBrain's ranking, not the adapter.
- This does not establish that GBrain, Ollama, or any embedding model is
  inadequate generally; it establishes that this pinned GBrain +
  local-embedding configuration does not meet the predeclared acceptance
  rule on this corpus.
- A hosted embedding fallback (for example Gemini) would require a new
  explicit instruction per the standing policy and was not used.

## Workload-fit note

The AMSB DEV corpus contains distinctive lexical identifiers/tokens, which
likely favors exact/keyword retrieval. In this workload, GBrain's controlled
keyword path ranked evidence substantially better than the tested semantic
embedding configurations. AMSB V1 is valid for its preregistered workload,
but these results should not be interpreted as a universal test of semantic
retrieval quality. This is a workload-fit limitation, not a benchmark
invalidation, and not evidence that semantic retrieval is generally inferior.

## What `forbidden_evidence_total` means

`forbidden_evidence_total` is the count, summed across all queries, of
retrieved evidence items whose corpus metadata kind is `poison_attempt`
(untrusted content planted in the corpus, sourced from external forum posts;
the DEV corpus contains three such events). It counts poison-kind items
present in the evidence set regardless of whether the reader cited them. It
does not count temporal/as-of-ineligible items, and it is not a security- or
deletion-leak metric. It is an exposure count for authority/poisoning cases.

## Stopping-rule record

The first DEV attempt (snowflake-arctic-embed:335m, Recall@5 0.7639) fell
below the preregistered 0.85 threshold. Attempts 2 and 3 were not part of
the original preregistration. They were executed under an explicit,
on-record user instruction for this completion attempt: the author proposed a
bounded DEV candidate set of recipe-asserted local embedding models (arctic
embed2 first, then bge-m3 if the guardrail still failed), and the user
responded: "proceed. Choose the best flow you think is right." After the
first DEV rejection, that bounded supplementary follow-up authorized two
additional local embedding configurations to test whether the result was
specific to the initial model. This was not an open-ended model search: both
additional configurations also failed the preregistered 0.85 DEV threshold,
after which testing stopped. The original predeclared rule ("if the
configuration is correct but local embedding performance remains below 0.85:
stop and report") applied to the bounded candidate set and was honored.

These runs are post-freeze supplementary evidence only. They are not merged
into frozen V1 tables, hidden TEST provider results, provider rankings, or
controlled/native benchmark headline numbers.

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
**Native DEV evaluated and rejected by the preregistered guardrail; hidden
TEST not run.** The pinned version technically supports local embeddings,
and all three tested configurations were operational on DEV with every
preflight/isolation check passing, but none met the preregistered
Recall@5 >= 0.85 DEV guardrail. The best result was 0.8194, so no
supplementary GBrain-native hidden-TEST run exists. Testing stopped after
the bounded candidate set, without a hosted-embedding fallback.

The result is specific to the tested GBrain version, local embedding
configurations, adapter surface, and AMSB DEV corpus. On this corpus,
GBrain's keyword path ranked relevant evidence better than the tested
embedding-backed path; it does not establish general inadequacy of GBrain or
semantic retrieval.
