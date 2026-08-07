# Memory Sovereignty Benchmark — Semantic Memory Exit v1

**Date:** 2026-08-07
**Repository commit used to generate findings:** `f69ba622c74089bd285571135f99660ebe687173`
**Frozen Task 15 report:** `docs/reports/task15-native-track-research-review.md`, commit `c3007f4`
**Frozen protocol:** `protocol-v1-freeze`; this report is additive and does not mutate V1.
**Follow-up protocol:** `sovbench/semantic-memory-exit/1`
**Experiment attempt:** `attempt-20260807T045318Z`
**Provider/model versions:** GBrain `15b9863d...` / v0.42.73.2; Mem0 OSS `3f39fba...` / v2.0.17; Hindsight `797faf7...` / v0.8.6; common native reader calls used `deepseek-v4-flash` through the existing gateway.
**Dataset:** 24 synthetic public events, 10 public queries; events SHA-256 `5f5db4ca2669bd7a3795b0109ebb53a00cd841b2298910260852908e186288f3`; queries SHA-256 `6403e20c880071ca57b5f6a0f4c83c89a9c44eceaf45264a468179fea93d5024`; private-gold SHA-256 `3ba638c39ba3b80df11e28d4dddee4974f544a1970a146a493cff22864b0cc06`.
**Repository status at report generation:** `?? docs/reports/gbrain-native-local-supplement.md
?? docs/reports/semantic-memory-exit-v1.md`

## 1. Executive Summary

This bounded experiment asked what trustworthy memory meaning survives when a
user keeps only the pinned product's documented/native exit artifact, the
original runtime is removed, and the product is reconstructed from that
artifact alone. It used 24 deliberately constructed source events covering
temporal state, authority, provenance, scope, deletion, supersession, and
model-derived facts. It did not create a general migration framework or a
recall leaderboard.

The strongest observation is Hindsight's pinned native export response: the
Category A artifact contained only `{"version":"1"}`, and import returned no
created or updated operations. This is a measured export-contract observation,
not proof that no internal state existed. It means the tested documented exit
surface did not expose the memory state needed for recovery.

Mem0's native `get_all` enumeration exposed 17 derived memories for 22
non-delete source events. It was machine-readable, but the native artifact
contained derived memory text and selected metadata rather than the canonical
raw event stream, validity intervals, supersession graph, or deletion
tombstones. Same-system reconstruction re-added 17 memories without rerunning
an LLM, but it was not a lossless raw-event recovery.

GBrain produced 20 human-readable Markdown pages. The tested import path
rebuilt a runtime but returned `No results` for all 10 recovery probes, so
human readability did not imply behavioral recovery. Its exported frontmatter
also reflected the benchmark adapter's selected metadata, not all semantic
event fields.

The evidence supports a layered architecture for user and enterprise memory:
retain a canonical, append-only, semantically rich event ledger under user or
organizational control, and treat memory products as rebuildable indexes or
derived views. It does not justify declaring one provider universally best or
claiming a general portability theorem.

## 2. Frozen V1 Context

Task 15 is treated as a completed, frozen V1. Its controlled and native tables
remain authoritative. The frozen report records controlled GBrain Recall@1
0.618 and Recall@5 0.982, BM25 Recall@5 1.0, native Mem0 Recall@1 falling from
0.600 controlled to 0.418 native, and native Hindsight changing from 0.709 to
0.727. Those facts are used as context only; no V1 result was recomputed or
merged with this follow-up.

The broad Tasks 16–20 roadmap remains stopped. This report covers only the
local-embedding GBrain feasibility follow-up and this small semantic-exit
experiment.

## 3. Exact Research Question

**If a user leaves a memory product and retains only the state that the product
legitimately lets the user keep, how much trustworthy memory meaning survives
after the original application state is gone?**

The experiment separates serialization fidelity, semantic/state fidelity,
behavioral recovery, and governance properties. A successful file copy is not
treated as successful semantic migration.

## 4. GBrain-Native Supplementary Result/Status

The exact pinned GBrain source supports Ollama embeddings. The selected local
model was `snowflake-arctic-embed:335m`, Ollama digest
`21ab8b9b0545e26a78164a910691440a3f1de1bfa41c3953d7451d52036c581a`, 1024
dimensions, Ollama 0.32.6. DEV preflight passed, but DEV Recall@5 was
0.7639, below the preregistered 0.85 guardrail. Hidden TEST was not run. The
complete additive report is [gbrain-native-local-supplement.md](gbrain-native-local-supplement.md).

## 5. Systems and Pinned Versions

| System | Pinned version | Exit path used | Native LLM during population |
|---|---|---|---|
| GBrain | 15b9863d... / 0.42.73.2 | pinned `gbrain export --dir` Markdown | none; local Ollama was embedding-only |
| Mem0 OSS | 3f39fba... / 2.0.17 | documented/native `Memory.get_all` enumeration per user | DeepSeek through gateway, `infer=True` |
| Hindsight | 797faf7... / 0.8.6 | pinned native bank `GET /export` | DeepSeek through gateway via internal sidecar |

The existing adapters add event metadata and lifecycle mapping. Those adapter
fields are reported as adapter-mediated evidence, not automatically as native
product guarantees.

## 6. Local Embedding Model and Reader Configuration

GBrain used only the local Ollama embedding model above. It did not run a local
generative model. Mem0 used its pinned local FastEmbed configuration while
native fact extraction used the common `deepseek-v4-flash` gateway. Hindsight
used its pinned local embedding/reranker images while native retain/recall
features used the gateway bridge. No gold answers were sent to any provider or
reader. No LLM judge was used for the exit experiment.

## 7. Synthetic Exit Dataset

The public corpus is `datasets/followups/semantic-exit-v1/`. It contains 24
events and 10 queries, with two principals (`alice`, `bob`), personal/shared
scopes, changed and historical claims, source/event time differences,
authority conflicts, deletion targets, a do-not-store instruction, native/model
inference, a multi-fact source event, a provenance chain, and an ambiguous
claim. Private semantic gold is under `scorer_private/semantic-exit-v1/` and
was never mounted in a provider directory.

## 8. Native Population Behavior

| System | Population operations | Pre-exit query probes | Observed native behavior |
|---|---|---|---|
| GBrain | 24/24 | 10 (10 returned records) | Markdown pages; deletion removed the targeted pages; no native extraction |
| Mem0 OSS | 24/24 | 10 (10 returned records) | 17 native derived memories enumerated across Alice/Bob; 22 source upserts were not preserved one-for-one |
| Hindsight | 24/24 | 10 (10 returned records) | hybrid native retrieval and retain/reflection calls; export response was version-only |

## 9. Exit Artifact Definition per Provider

Category A is the primary result: the documented/native surface a technically
capable user could call. GBrain was a Markdown export; Mem0 was native
`get_all`, not the adapter's private event registry; Hindsight was the pinned
bank export endpoint. Category B is a separate copy of run-owned raw state
where practical: GBrain raw brain/PGLite files and Mem0 Chroma/history files;
no Hindsight database volume was treated as a user export.

| System | Category A artifact | Human-readable | Hash |
|---|---|---|---|
| gbrain | GBrain Markdown export | True | bddd051ac46d78c3ed09a36f1de02d63188486b98e9d9661a7b6194390bfa277 |
| mem0 | Mem0 get_all results | False | 74c3211e72c0f183d10f16fed06959c5a41400cc1dc996c423b5aba792a91ea3 |
| hindsight | Hindsight bank export JSON | True | 2e8ed30685082ace922bded8a0d12aedd3dfd5111819170d0cd5a8f554fb038a |

## 10. What Was Retained and Destroyed

The retained Category A artifact and its hash remained outside the original
runtime. Category B was retained only as separately labelled disaster-recovery
evidence. Original provider data directories were removed and verified absent.
For Hindsight, the native bank was deleted and the experiment-specific Docker
project and volume were removed before fresh recovery. The first GBrain cleanup
attempt hit a Windows access-denied lock; the exact run-owned directory was
removed and re-verified after the process ended. This is recorded as
`post_run_cleanup_verified`, not hidden.

| System | Original runtime destroyed | Recovery runtime | Raw Category B |
|---|---|---|---|
| gbrain | True | recovered | True |
| mem0 | True | recovered | True |
| hindsight | True | recovered | False |

## 11. Semantic Export Fidelity Matrix

The following is a count of per-event classifications, not a composite score.
It is intentionally exposed dimension by dimension.

| Property | GBrain | Mem0 OSS | Hindsight |
|---|---|---|---|
| authority | PRESERVED=24 | LOST=2, PRESERVED=22 | LOST=24 |
| current_state | NOT OBSERVABLE=4, PRESERVED=20 | NOT OBSERVABLE=24 | NOT OBSERVABLE=24 |
| deletion_state | LOST=2, NOT OBSERVABLE=22 | LOST=2, NOT OBSERVABLE=22 | LOST=2, NOT OBSERVABLE=22 |
| derived_memory | NOT OBSERVABLE=4, PRESERVED=20 | NOT OBSERVABLE=24 | NOT OBSERVABLE=24 |
| explicit_user_vs_model_derived | DEGRADED=5, PRESERVED=19 | DEGRADED=7, PRESERVED=17 | DEGRADED=24 |
| factual_content | LOST=4, PRESERVED=20 | LOST=24 | LOST=24 |
| historical_state | NOT OBSERVABLE=21, TRANSFORMED BUT EQUIVALENT=3 | NOT OBSERVABLE=24 | NOT OBSERVABLE=24 |
| original_source | PRESERVED=24 | LOST=2, PRESERVED=22 | LOST=24 |
| principal_scope | PRESERVED=24 | PRESERVED=24 | DEGRADED=24 |
| provenance | PRESERVED=24 | NOT OBSERVABLE=2, PRESERVED=22 | NOT OBSERVABLE=23, PRESERVED=1 |
| raw_source_event | DEGRADED=20, LOST=4 | LOST=24 | LOST=24 |
| source_timestamp | LOST=24 | LOST=16, PRESERVED=8 | LOST=24 |
| supersession | LOST=1, PRESERVED=3, UNSUPPORTED=20 | LOST=1, PRESERVED=3, UNSUPPORTED=20 | LOST=4, UNSUPPORTED=20 |
| valid_from | LOST=11, UNSUPPORTED=13 | LOST=3, PRESERVED=8, UNSUPPORTED=13 | LOST=11, UNSUPPORTED=13 |
| valid_to | LOST=3, UNSUPPORTED=21 | LOST=3, UNSUPPORTED=21 | LOST=3, UNSUPPORTED=21 |

The Hindsight `version=1` artifact makes most properties `LOST` or `NOT
OBSERVABLE`; that is a property of the observed native exit response. The
GBrain and Mem0 preservation of authority, source, principal, and scope must
be read with the adapter caveat: those fields were supplied by the benchmark
adapter and are not proven native guarantees.

## 12. Same-System Recovery Results

| System | Recovery action | LLM required | Behavioral result |
|---|---|---|---|
| GBrain | Import exported Markdown into a fresh pinned GBrain and run 10 CLI searches | False | Runtime rebuilt, but all 10 searches returned `No results` |
| Mem0 OSS | Re-add 17 enumerated memories with `infer=False` | False | Fresh Chroma index rebuilt; native-ID probes recorded after recovery |
| Hindsight | Import native bank export into a fresh bank | False | Import returned no created/updated operations; post-import recall probes were recorded |

The GBrain result is an important failure to interpret carefully: the artifact
was readable, but the tested pinned import command did not restore observable
search behavior. This may involve source routing, index rebuild semantics, or
adapter/import interaction; it is not enough evidence to assign the cause to
GBrain alone.

## 13. Recovery Nondeterminism

The exit recovery path did not rerun an LLM: Mem0 memories were re-added as
already derived text, GBrain imported Markdown, and Hindsight used the native
import endpoint. Therefore three-repeat regeneration variance was not
applicable to this exact recovery path. Native population itself used one
replicate per provider, so extraction/consolidation nondeterminism was observed
qualitatively but not estimated statistically. A future regeneration study
would need at least three independent recoveries and must not call them
lossless recovery.

## 14. Cross-System Migration Result

No cross-system migration was justified. Same-system exit already exposed
unresolved source-export and recovery failures, while a conversion pair would
have added an adapter-defined mapping and risked hiding whether loss occurred
before serialization or at the destination. No generalized migration code was
built.

## 15. Provenance Fidelity

The synthetic corpus included a source chain for ATLAS-42 and source identifiers
for user, policy, webpage, assistant, and calendar records. GBrain and Mem0
artifacts retained source strings in the tested export shape; Hindsight's
version-only Category A artifact exposed no source state. However, GBrain and
Mem0 source retention was carried through benchmark metadata. The result is
**adapter-mediated preservation**, not proof of a product-native provenance
contract.

## 16. Authority Fidelity

The corpus deliberately conflicted an untrusted webpage with a signed release
policy. The live pre-exit adapters could return both deployment claims, while
the private gold identifies the policy as authoritative. The GBrain/Mem0
exported metadata retained the authority labels supplied by the adapter;
Hindsight's primary export did not expose them. The experiment cannot claim
that the products independently preserve or enforce authority semantics.

## 17. Explicit-User vs Model-Derived Fidelity

The corpus separated explicit user statements from assistant inference and
included an explicit erasure target for a derived claim. Mem0 native extraction
created derived memories, but its `get_all` output did not provide a complete
raw-event-to-derived-memory audit trail. GBrain preserved the adapter's
`authority` field because it was written to frontmatter. Hindsight's version-only
export made this property not observable. No provider's Category A result
should be interpreted as a complete model-inference provenance ledger.

## 18. Temporal and Supersession Fidelity

The source events carried `valid_from`, `valid_to`, `available_at`, correction,
and supersession links. The tested GBrain and Mem0 adapter metadata did not
include all validity or supersession fields, so temporal history was commonly
lost or not observable in Category A. Hindsight's version-only export provided
no evidence of these fields. Retrieval before exit was filtered by the
benchmark adapter and therefore does not prove that native export preserves
as-of or historical-state semantics.

## 19. Scope and Access-Control Fidelity

The experiment used Alice personal, Bob personal, and Atlas shared scope. The
pre-exit adapter queries recorded no provider operation failure, but the
cross-principal behavior was adapter-mediated. Mem0 native `get_all` was
enumerated separately for Alice and Bob. Category A retention of principal and
scope was visible for GBrain/Mem0 through adapter-added metadata and absent in
Hindsight's version-only export. Export portability must therefore be tested
with access-control semantics, not just text files.

## 20. Deletion and Erasure Fidelity

Two explicit delete operations targeted an untrusted external note and an
assistant-inferred claim. The live providers removed the targeted state through
their tested lifecycle calls. No Category A artifact contained a complete
deletion/tombstone record: deletion state was `LOST` for the delete events in
the matrix. The experiment did not find evidence that deleted information
returned after the fresh same-system reconstructions, but Hindsight's empty
export and GBrain's failed search recovery limit the strength of that negative
finding.

## 21. Human Readability

GBrain's Markdown export was directly inspectable and carried page frontmatter
plus text. Hindsight's JSON response was syntactically human-readable but
semantically empty beyond `version=1`. Mem0's JSON `get_all` enumeration was
machine-readable but included generated IDs, hashes, timestamps, and derived
memory text rather than a clean source-event ledger. Human readability and
semantic completeness are separate properties.

## 22. Rebuildability

GBrain and Hindsight accepted a fresh runtime construction path, but the tested
GBrain import produced no search results and Hindsight import produced no
operations. Mem0 rebuilt a Chroma index from 17 derived memories without an
LLM, but raw-event reconstruction and exact native memory identity were not
available from Category A alone. Index rebuildability is therefore not the
same as application-state or semantic rebuildability.

## 23. Costs and Latency

The final complete attempt used no reader judge. Final-attempt ledgered native
calls were approximately Mem0 22 and Hindsight
45; GBrain used no DeepSeek calls. Across
all additive follow-up attempts, the ledger accounts for
1,061,908 input tokens, 192,042 output
tokens, and approximately **$0.202439** at the configured DeepSeek
accounting rates. This includes the corrected reruns and excludes no observed
ledgered usage. Provider latency was recorded per population/query operation
in the machine observations; no composite latency score is reported.

## 24. Failure Analysis

Observed issues are categorized as follows:

- **Harness/configuration failure:** the first semantic attempt used a gateway
  requiring request identity headers that native clients do not send. It was
  stopped, preserved as an incomplete attempt, and excluded from findings;
  Task 15's stamped native gateway mode was applied in the corrected run.
- **Lifecycle/infrastructure failure:** the first GBrain destruction pass hit a
  Windows directory-lock/access-denied condition. The exact runtime was removed
  after process completion and verified absent.
- **Provider/export behavior:** Hindsight's native export response was
  version-only; GBrain import produced no search results; Mem0 exposed derived
  rather than raw event state.
- **Dependency warning:** Mem0 reported that optional spaCy lemma/full models
  were not installed. The pinned native run still completed; this warning is
  recorded and not silently normalized away.

No provider population operation failed in the corrected completed attempt.

## 25. Existing Standards and Prior Work Comparison

The frozen V1 research review already compared LongMemEval, LoCoMo, BEAM, AMB,
MemTools, STATE-Bench, GateMem, MemSecBench, AuthMem-Bench, SovereignPA-Bench,
memorywire/AMP, and IETF AI memory-interchange work. This follow-up reuses that
context rather than claiming a new benchmark category.

Those efforts do better at task-level memory evaluation, security/governance
framing, or proposed interchange semantics. The present experiment measures a
narrow property they do not automatically establish: what the pinned product
actually exposes through its documented/native exit path and whether a fresh
same-system runtime can recover state from that artifact. It does not prove
that an existing interchange format could not preserve the missing properties.

Any future interoperability claim should first test memorywire/AMP or an
applicable IETF interchange representation against this same private gold.

## 26. Limitations

This is 24 synthetic events, one native population replicate, three pinned
providers, and one machine. It uses existing adapters that add metadata and
post-filter retrieval; native product guarantees are not isolated from adapter
behavior. The Hindsight export contract was observed through the pinned
endpoint response, but its internal database is not reverse-engineered here.
The GBrain import probe used the pinned CLI path and observed no results, but
source routing/index behavior deserves independent confirmation. No LLM
regeneration variance, catastrophic application restore, or cross-system
migration was measured. These limits prevent a universal provider ranking.

## 27. Reproduction Instructions

The source corpus and private gold commitments are listed above. The corrected
runner command was:

```powershell
$env:SOVBENCH_PROTOCOL_COST_APPROVED = "1"
$env:GBRAIN_BIN = "%USERPROFILE%\.bun\install\global\node_modules\gbrain\src\cli.ts"
$env:BUN_BIN = "%USERPROFILE%\.bun\bin\bun.exe"
$env:OLLAMA_BASE_URL = "http://127.0.0.1:4713/v1"
$env:OLLAMA_HOST = "127.0.0.1:4713"
$env:PYTHONPATH = ".venv\Lib\site-packages"
python scripts/run_semantic_memory_exit.py
```

Generated observations are under `runs/followups/semantic-exit-v1/attempt-20260807T045318Z`;
the redacted report is this file. The private gold is not a provider artifact.

## 28. Personal/Project-Memory Recommendation

Based on this evidence, if the priority is to change AI agents or memory
software later without losing trustworthy accumulated memory, choose a
**layered approach**: keep a user-controlled canonical event ledger containing
raw source text, timestamps, validity, authority, provenance, principal/scope,
supersession, and deletion/tombstone state; use GBrain, Mem0, or Hindsight as
rebuildable indexes/derived views with an export receipt.

If forced to choose a product layer only, GBrain is the most human-readable
tested exit artifact, but its tested import did not recover behavior. Mem0
offers a practical native enumeration but exposes derived memories rather than
the full source ledger. Hindsight's observed native export was insufficient for
the exit question. None earns a standalone sovereignty recommendation.

## 29. Enterprise-Memory Recommendation

Enterprise use should require vendor independence through a separately owned
canonical ledger and periodic export drills. The ledger must preserve
provenance, authority, temporal history, access-control scopes, deletion and
tombstone state, and an auditable source-to-derived-memory relationship.
Providers may serve retrieval and consolidation, but their indexes should be
rebuildable and disposable. Disaster recovery must test a fresh environment,
not merely the continued availability of the original database volume.

## 30. Final Continue/Stop Recommendation

**Recommendation 2 — PUBLISH V1 + ONE SMALL FOLLOW-UP.** Publish the frozen V1
benchmark together with this narrowly scoped exit reconnaissance, with explicit
adapter and export-contract caveats. Stop the broad Tasks 16–20 roadmap now.
The observed Hindsight export gap, Mem0 derived-state gap, and GBrain
human-readable-but-nonrecovering result are useful enough to publish as
measured engineering evidence, but they do not justify more providers,
enterprise corpora, STATE-Bench integration, or a generalized migration layer
in this project.

The one unresolved human-review decision is whether to perform a separate
manual confirmation of the pinned Hindsight export/import contract before
making public wording stronger than “the tested native endpoint returned a
version-only artifact.”

## Appendix: Machine Evidence and Warnings

- Semantic attempt: `attempt-20260807T045318Z`.
- GBrain supplementary analysis: `runs/followups/gbrain-native-local/dev-analysis.json`.
- GBrain attestation: `runs/followups/gbrain-native-local/environment-attestation.json`.
- Frozen V1 report: `docs/reports/task15-native-track-research-review.md`.
- Public exit corpus: `datasets/followups/semantic-exit-v1/`.
- Private gold: `scorer_private/semantic-exit-v1/gold.json`.
- No Graphiti, Cognee, MIND-Mem, enterprise corpus, STATE-Bench, or broad
  migration tooling was added.
- The first identity-misconfigured attempt is retained as an incomplete
  diagnostic artifact and is not included in the final result tables.
