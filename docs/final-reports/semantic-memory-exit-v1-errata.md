# Memory Sovereignty Benchmark — Semantic Memory Exit v1 Errata

**Date:** 2026-08-07
**Original experiment record:** `docs/reports/semantic-memory-exit-v1.md`
**Original experiment source commit:** `f69ba622c74089bd285571135f99660ebe687173`
**Post-freeze report commit:** `80288f5e402b9b8a20a46568e00ddd494433afd3`
**Frozen Task 15 report:** `c3007f4`
**Corrected evidence root:** `runs/followups/semantic-exit-v1-correction/` (ignored run artifacts; not part of the public report)

This file is an explicit correction trail. The original report remains intact and is not silently rewritten. The corrected report is a separate document and uses only the evidence identified below.

## What the original experiment did

The original 24-event semantic-exit experiment asked what meaning survives when a user retains only a documented or native exit artifact, destroys the original runtime, and reconstructs a fresh instance. It used the same pinned providers and synthetic corpus later reused for the forensic pass.

The original interfaces and findings were:

| Provider | Original interface | Original observation | Status after review |
|---|---|---|---|
| Hindsight v0.8.6 | HTTP `GET /v1/default/banks/{bank}/export` | Artifact contained only `{"version":"1"}`; no useful whole-bank recovery was observed | **Retracted as a product-exit conclusion.** This was the wrong export surface. |
| GBrain v0.42.73.2 | `gbrain export --dir` followed by fresh `gbrain import` | 20 Markdown pages were present, but all ten recovery searches returned `No results` | **Retracted as evidence of unrecoverable canonical state.** The recovery procedure omitted source registration/routing and the documented sync/index sequence. |
| Mem0 OSS v2.0.17 | `Memory.get_all()` only | 17 current derived memories were enumerated and re-added without an LLM | **Incomplete, not wholly false.** The documented `Memory.history(memory_id)` surface was not included. |

## Issues under review

The purpose of the review was to distinguish a benchmark or configuration mistake from a documented product limitation. The correction did not upgrade a provider, patch upstream code, tune the corpus, or alter the frozen Task 15 protocol.

### Issue 1 — Hindsight whole-bank export/import

**Root cause:** harness/interface mistake.

The pinned v0.8.6 source contains `hindsight-admin export-bank` and `hindsight-admin import-bank`. The former produces a portable ZIP containing bank configuration, documents, facts, observations, mental models, directives, webhooks, and a manifest. Embeddings are intentionally omitted and regenerated on import. The matching importer rebuilds links and indexes and re-embeds facts; it does not rerun LLM extraction.

The original HTTP response was a different endpoint and was not the pinned whole-bank transfer mechanism. An adapter-independent smoke test inserted a distinctive memory, exported it with `hindsight-admin export-bank`, destroyed the runtime, imported with the matching command, and recovered the marker. The corrected 24-event run exported 20 documents, 20 facts, and 15 observations and recovered all ten bounded probes without errors.

**Correction:** retract the original statement that Hindsight's documented exit artifact was empty or version-only. The corrected claim is narrower: the real whole-bank artifact supports same-system recovery, but it does not by itself provide a lossless event ledger. Deleted source events are not present in the retained artifact, operational history is optional and was not included, and several temporal/supersession properties are not represented as a complete native semantic model. Metadata that the benchmark adapter supplied must not be presented as a native governance guarantee.

**Corrected evidence:** `attempt-20260807T065643Z`; independent smoke evidence under `hindsight-smoke/`; pinned source commit `797faf7981ce9332e2ce7c922471b72b506b4065`.

### Issue 2 — GBrain canonical-state recovery

**Root cause:** recovery configuration/procedure mistake.

The pinned source distinguishes the Git/Markdown brain from derived PGLite pages, chunks, embeddings, and search indexes. The generated `gbrain export --dir` artifact is not automatically the same as a configured source repository. A fresh recovery must initialize the pinned runtime, register the source, establish default routing, then run `sync` or the matching import/reindex path so pages and embeddings are rebuilt.

The original run had Markdown files but did not reproduce that source-registration and index-rebuild contract. The corrected independent smoke test recovered three pages through both the canonical Git/Markdown path and the generated export path. The corrected 24-event run recovered 20 pages, 20 chunks, 100% embedding coverage, and ten of ten bounded probes through each path.

**Correction:** retract the original claim that the tested GBrain export was behaviorally unrecoverable. The corrected claim is that GBrain has two distinct exit surfaces: the canonical Git/Markdown brain, which is the durable source of truth in the pinned implementation, and the generated `gbrain export --dir` Markdown artifact. Both were recoverable in this correction when the pinned source was registered and the derived indexes were rebuilt. The test does not prove that every future GBrain version or arbitrary copied directory will recover without that sequence.

**Correction boundary:** this pass did not revisit the failed V1 supplementary embedding-quality gate. It used the same pinned local Ollama configuration only as recovery infrastructure and did not run hidden TEST for that embedding experiment.

**Corrected evidence:** `attempt-20260807T063919Z`; pinned source commit `15b9863d13635d173562a54f55a1d388bfcf546b`.

### Issue 3 — Mem0 maximal documented OSS exit state

**Root cause:** incomplete interface coverage, plus one corrected harness call.

The original artifact used `Memory.get_all()` only. The pinned v2.0.17 OSS package also exposes `Memory.history(memory_id)`. The corrected artifact collected history for every memory currently returned by `get_all()`, without adding the benchmark adapter's private raw-event registry to the primary artifact. No official OSS export/import implementation beyond these interfaces was found in the pinned source; hosted-platform export features were not attributed to OSS.

The corrected recovery also removed an unsupported `reference_date` argument. The pinned OSS SDK explicitly rejects that argument, so the initial post-exit query errors were a harness mistake and are not provider failures. The corrected recovery used the documented search surface without as-of semantics and made that limitation explicit.

**Correction:** the original conclusion that `get_all()` exposes derived state while losing raw source identity remains directionally correct, but it was incomplete. `get_all()+history` preserves native creation/update history for the 17 currently enumerable memories. It does not provide an export-wide history enumeration, raw source-event stream, stable IDs after re-add, reconstructible tombstones for deleted IDs, or a native source-to-derived lineage contract. All 17 history arrays in this run contained `ADD` rows; the artifact therefore supplies no observed update/delete history for the enumerated memories.

**Corrected evidence:** `attempt-20260807T065850Z`; pinned source commit `3f39fba28f7781aaf581f64a4af39d017af65835`.

## Findings retained after correction

The forensic pass does not turn the experiment into a provider ranking. The following conclusions survive:

1. Same-system recovery, semantic portability, and behavioral portability are different properties.
2. Hindsight's correct native whole-bank transfer recovers a functioning same-system bank, but its archive is not equivalent to a complete user-owned semantic event ledger.
3. GBrain's canonical source and derived indexes must be distinguished. Correct recovery works when the source contract is followed.
4. Mem0 OSS exposes a useful current derived-memory enumeration and per-memory history, but the documented OSS surface is not an export-wide source/history/tombstone contract.
5. Provenance, authority, principal, scope, and temporal metadata observed in the benchmark are frequently adapter-supplied. They cannot be counted as native product guarantees without native evidence.
6. A layered design remains the most defensible personal and enterprise recommendation: keep a user- or organization-controlled canonical ledger and treat provider state as rebuildable derived state.

## Findings explicitly retracted

- “Hindsight's documented/native exit artifact was only `{"version":"1"}`.” **Retracted.** It described the wrong HTTP surface, not the pinned whole-bank mechanism.
- “Hindsight whole-bank import returned no useful recovery.” **Retracted.** The matching admin import recovered the corrected bank.
- “GBrain's Markdown export failed behavioral recovery.” **Retracted as a provider conclusion.** The earlier procedure was incomplete; both corrected recovery paths worked.
- “Mem0's maximal documented OSS exit surface is `get_all()` alone.” **Retracted.** History was omitted from the original experiment and is included in the corrected result.

## Scope and reproducibility

The corrected runs did not alter `protocol-v1`, the frozen Task 15 report, the original semantic-exit report, the corpus, or private gold. No new providers, large datasets, cross-system migration matrix, or generalized migration framework were added. Corrected run manifests and hashes remain in ignored local run artifacts; the public reports contain only redacted summaries and relative evidence references.
