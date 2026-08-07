# Phase 0 Methodology Audit

**Date:** 2026-08-05  
**Auditor:** Codex  
**Scope:** Commit `3c15a91` (`Phase 0: Memory Sovereignty Benchmark harness + baselines`)  
**Authority:** The canonical Notion page remains the source of truth. This audit records where the implementation diverges from it.

## Executive finding

Phase 0 is a useful plumbing prototype, but it is not yet a valid benchmark harness and must not produce publishable comparative results. The 42 original tests pass because they assert the current implementation, not all of the research invariants. The highest-risk defects are fail-open preflight behavior, ingestion of future events before historical queries, non-blocking snapshot failures, misleading model manifests, and dataset semantics that conflate the memory owner, the requester, and the person a fact is about.

No provider result has been published, so these defects are recoverable without invalidating a public claim.

## Confirmed defects and dispositions

| ID | Severity | Finding | Why it matters | Phase 0 disposition |
|---|---:|---|---|---|
| P0-01 | Critical | Required preflight failures are logged as “aborting,” but `run_baseline` continues through ingestion, retrieval, scoring, and a “run complete” log entry. | A contaminated run can look complete and acquire scores. | Fail closed before ingestion; write an `aborted_preflight` manifest with no scores or traces. |
| P0-02 | Critical | The runner ingests the corpus once at the global August clock and reuses that state for February/March/July questions. | A provider can consolidate future events into past state even if its final retrieval filters `available_at`. | Build a separate baseline snapshot for every distinct `as_of` checkpoint using only events available by that checkpoint. |
| P0-03 | Critical | A failed restore hash and query-time state mutation are recorded but do not invalidate the query or run. | Scores can be produced from the wrong or contaminated state. | Raise a run-invariant failure before reader/scorer execution; record an invalid run. |
| P0-04 | Critical | Offline manifests identify the reader provider as DeepSeek and the model as `deepseek-v4-flash`, although the actual reader is `stub-offline`. | The run record misstates which model produced the answer. | Record requested model, actual gateway, actual model, returned model, API request ID, and validation scope separately. |
| P0-05 | High | The official API response `id` is stored as `response_model_id`; retry count is discarded. | Model identity and retry/cost accounting are wrong. | Read model identity from the response `model` field, preserve request ID separately, and return the actual retry count. |
| P0-06 | High | The offline oracle control verifies only evidence presence; its reader answer score is not meaningful. The no-memory control also tests a hard-coded stub, not model leakage. | The harness can claim reader validation without ever calling a semantic reader. | Label offline runs `plumbing_only`, suppress semantic reader metrics, and require a small official-API preflight before a run is publishable. |
| P0-07 | High | Evidence sent to the reader omits real evidence IDs and core provenance/time/authority metadata. It can report numeric display positions rather than auditable source IDs. | Authority, provenance, temporal validity, and citation correctness cannot be evaluated. | Serialize canonical evidence records with item ID, score, subject/owner, scope, authority, source, availability, validity, and text. |
| P0-08 | High | Truncation reports every retrieved item ID even when later items were not included in the reader context. | Reader-context accounting and evidence attribution are false. | Budget item-by-item and record only included IDs plus omitted count. |
| P0-09 | Critical | `principal` simultaneously means memory owner/requester and the person described by a fact. | Cross-user isolation is artificially easy and the multi-hop case is structurally impossible. | Keep `principal` as the requesting memory owner for compatibility; add an explicit event/query `subject`. Regenerate DEV so normal facts share one owner while describing distinct synthetic people. |
| P0-10 | Critical | The roommate multi-hop gold lists only the roommate’s preference event, not the relationship edge. | Oracle evidence is insufficient to answer the question from supplied evidence alone. | Include the full minimal evidence chain in gold. |
| P0-11 | High | “Starting in September” is encoded as `valid_to=September`; preference changes omit some `supersedes` links. | Temporal truth metadata is internally wrong. | Correct validity direction and supersession links; lint all generated records. |
| P0-12 | Critical | “Do not remember” and deletion requests are ingested as ordinary text containing the very value that should be removed. No delete lifecycle action executes. | The cases test lexical accidents, not erasure. | Represent lifecycle actions structurally, execute them during chronological ingestion, and never index the deletion-request payload as memory content. |
| P0-13 | High | Canary isolation resets a single store, writes only its own canary, and then confirms absent canaries are absent. | It does not prove cross-provider volume isolation. | Restrict the in-process check to namespace hygiene; require a two-run persistent-volume canary probe for container adapters. Do not call the in-process check proof of container isolation. |
| P0-14 | High | Network isolation is a string search for `internal: true`; gold inaccessibility is only a path-overlap check. | Static declarations are not runtime enforcement evidence. | Split static policy validation from runtime probes and mark in-process controls as non-container evidence. Provider publication runs require runtime denial tests and mount inspection. |
| P0-15 | High | The Docker gateway and clean-room script are placeholders. | The repository claims a clean-room setup that cannot yet route controlled model traffic or execute runtime preflight. | Describe them as a policy scaffold, not an established clean room. Complete runtime enforcement in the next implementation phase. |
| P0-16 | High | The documented Python 3.12/WSL2/`uv` target is not locked; the audited run uses Windows Python 3.11 and has no `uv.lock`. | Third parties cannot recreate an exact environment. | Add a pinned Python version and lock file before any provider comparison. Phase 0 correction may remain dependency-free but must report the exact host truthfully. |
| P0-17 | Medium | A four-characters-per-token estimate is treated as token accounting and can split evidence mid-record. | Context parity may differ from the actual model tokenizer. | Name and version the estimator, preserve record boundaries, log actual API usage when available, and treat estimates as estimates. |
| P0-18 | High | Retrieval “presence” is substring matching and answer scoring is a single exact-normalized string. | False positives, aliases, lists, dates, and structured answers are mishandled. | Make evidence-chain ID recall the primary deterministic retrieval measure; add typed acceptable answers to the dataset before final evaluation. |
| P0-19 | High | There is no dataset schema validation for duplicate IDs, missing gold, future gold, impossible evidence chains, or gold leakage. | Silent corpus errors can become provider “failures.” | Add a corpus validator and make it a preflight gate. |
| P0-20 | High | The run has no explicit `completed`, `aborted`, or `invalid` status and cleanup is not protected by `finally`. | Partial runs can be mistaken for completed runs and resources can remain live. | Add status/reason fields, atomic artifact writes, and guaranteed cleanup. |
| P0-21 | Medium | Provider versions are adapter constants, not upstream commits/image digests; SQLite snapshots use only physical file bytes. | Provider identity and semantic state reproducibility are weak. | Record adapter version separately from upstream identity; add canonical logical state hashes for baselines. |
| P0-22 | Medium | Single-run point estimates have no repeated-run or uncertainty protocol. | Rankings may overstate noise and tiny differences. | The remaining-phases plan specifies deterministic repeat policy, paired bootstrap intervals, failure-rate reporting, and no rank claims for overlapping uncertainty. |

## DeepSeek model identity correction

The official DeepSeek name is **DeepSeek-V4-Flash-0731**, accessed through the rolling API alias `deepseek-v4-flash`. DeepSeek’s official 2026-07-31 changelog says the update applies to V4 Flash, while V4 Pro and the app/web models were unchanged. No official source reviewed for this audit defines a model named “DeepSeek V4 Plus 07-31.” “Plus” must therefore be treated as an unverified UI or routing label until the serving provider attests what it maps to.

Publication runs must record:

- the user-facing label;
- the API provider and endpoint;
- the requested API model string;
- the model value returned in the response;
- the dated release expected by the protocol;
- the request timestamp and request ID;
- thinking/reasoning settings, temperature, top-p, seed if supported, and all retry behavior.

Primary sources:

- [DeepSeek API changelog, 2026-07-31](https://api-docs.deepseek.com/updates/)
- [DeepSeek API quick start](https://api-docs.deepseek.com/guides/reasoning_model)
- [DeepSeek-V4-Flash-0731 model card](https://huggingface.co/deepseek-ai/DeepSeek-V4-Flash-0731)

## Scientific guardrail

Phase 0 output is infrastructure evidence, not a provider leaderboard. A run becomes publication-eligible only when its manifest says `status=completed`, every required runtime preflight is applicable and passed, the corpus validator passes, the reader checkpoint is attested, and the scoring protocol was frozen before the hidden test split was opened.
