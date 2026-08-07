# Post-Freeze Supplementary GBrain-Native Local-Embedding Run

**Status:** `POST-FREEZE SUPPLEMENTARY GBRAIN-NATIVE LOCAL-EMBEDDING RUN`
**Generated:** 2026-08-07T05:10:29Z
**Repository state used for this report:** `f69ba622c74089bd285571135f99660ebe687173`
**Frozen V1 baseline:** Task 15 report commit `c3007f4`; frozen protocol/results were not modified.
**Protocol:** `post-freeze-followup-v1`; hidden TEST was not touched.

## Decision

The exact pinned GBrain source supports Ollama embeddings. The chosen local
configuration passed the isolation/preflight checks and completed a DEV-only
run, but DEV Recall@5 was **0.7639**, below the predeclared
0.85 acceptance guardrail. The local configuration is therefore rejected for
the supplementary hidden TEST run. No hosted embedding fallback, Gemini call,
GBrain upgrade, or protocol-v1 change was made.

## Exact pinned capability finding

The inspected GBrain source was commit `15b9863d13635d173562a54f55a1d388bfcf546b` / version
`0.42.73.2`. Its pinned source includes the Ollama recipe and
the `--embedding-model ollama:<model> --embedding-dimensions N` initialization
path. This conclusion is based on the pinned source, not current master.

## Configuration attestation

| Field | Observed value |
|---|---|
| GBrain | 15b9863d13635d173562a54f55a1d388bfcf546b / 0.42.73.2 |
| Ollama | ollama version is 0.32.6 |
| Embedding model | snowflake-arctic-embed:335m |
| Embedding digest | 21ab8b9b0545e26a78164a910691440a3f1de1bfa41c3953d7451d52036c581a |
| Dimensions | 1024 |
| Ollama endpoint | http://127.0.0.1:4713 |
| Reader | deepseek-v4-flash through the ledgered gateway |
| Reader local | False |
| Hidden TEST touched | False |

The embedding model was `snowflake-arctic-embed:335m`, 334M parameters, F16,
1024 dimensions, embedding capability only. The initially pulled
`snowflake-arctic-embed2:latest` was not scored because it stalled while
loading alongside GBrain/PGLite; it was not used as a fallback.

## DEV result

The existing DEV personal split was run with the common `deepseek-v4-flash`
reader, unchanged prompt, evidence budget, clock, and scoring. The optimized
preflight passed. The run completed 80 DEV queries with one follow-up
replicate.

| Metric | GBrain local DEV |
|---|---|
| abstain_accuracy | 0.95 |
| attempts | 80 |
| cross_principal_evidence_total | 0 |
| deleted_evidence_total | 0 |
| evidence_id_precision | 0.6354 |
| evidence_id_recall | 0.7639 |
| forbidden_evidence_total | 41 |
| gold_evidence_recall@5 | 0.7569 |
| mean_latency_ms | None |
| reader_accuracy | 0.775 |
| recall@1 | 0.4028 |
| recall@10 | 0.7778 |
| recall@5 | 0.7639 |
| runs | 1 |

The required guardrail is not a tuning target. It exists to identify an
obviously broken or badly mismatched local retrieval configuration before any
hidden TEST use. Here the configuration was operational and semantically
retrieving, but not strong enough for a defensible hidden comparison under the
predeclared rule.

## Comparison with the frozen V1 evidence

The frozen controlled V1 report records GBrain at Recall@1 = 0.618 and
Recall@5 = 0.982 under its no-embedding/keyword configuration. It records
BM25 Recall@5 = 1.0 and shows that rank-1, not top-5, is the more discriminating
retrieval dimension. The local-embedding DEV result is not directly comparable
as a hidden-test result, but its lower DEV Recall@5 shows that this particular
local model/configuration did not preserve the controlled GBrain behavior.

This does **not** establish that GBrain is bad, that Ollama embeddings are
generally inadequate, or that hosted embeddings would behave the same. It
only establishes that this pinned GBrain + this pinned local model + this
adapter + this DEV workload did not meet the preregistered acceptance rule.

## Controls and contamination checks

All 11 required preflight results passed. The in-process network check was
marked not applicable and made no container-egress claim. Static compose policy,
gold separation, fresh state, canaries, cross-principal isolation, future
filtering, query mutation, and reader statelessness passed. The no-memory probe
abstained on 5/5 synthetic secrets with zero leakage; the oracle control checked
72 non-abstain queries with zero incomplete evidence chains.

The provider used a separate follow-up root. No hidden TEST artifact, hidden
gold, or V1 result path was used. The reader remained remote DeepSeek; Ollama
was embedding-only.

## Cost and reproducibility

All follow-up gateway activity is ledgered. Across the DEV probes and the
incomplete/restarted DEV attempts, the follow-up GBrain ledger accounts for
366,946 input tokens and 76,976 output
tokens in the combined follow-up accounting; the total additional accounting
for this report and the semantic-exit follow-up is reported in the semantic
exit report. No hidden TEST API calls were made for GBrain.

Machine-readable evidence is in the ignored `runs/followups/gbrain-native-local/`
directory, especially `dev-analysis.json` and
`environment-attestation.json`. The reproducible command was:

```powershell
$env:GBRAIN_BIN = "C:\Users\haris\.bun\install\global\node_modules\gbrain\src\cli.ts"
$env:BUN_BIN = "C:\Users\haris\.bun\bin\bun.exe"
$env:OLLAMA_BASE_URL = "http://127.0.0.1:4713/v1"
$env:OLLAMA_HOST = "127.0.0.1:4713"
$env:SOVBENCH_PROTOCOL_COST_APPROVED = "1"
python scripts/run_gbrain_native_local.py --split dev
```

## Final GBrain follow-up status

**No hidden TEST supplementary GBrain-native local-embedding result exists.**
The correct status is: technically supported, DEV-validated as operational,
rejected by the preregistered Recall@5 guardrail, and stopped without a
hosted-embedding fallback.
