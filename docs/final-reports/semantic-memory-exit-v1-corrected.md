# Memory Sovereignty Benchmark — Semantic Memory Exit v1 (Corrected)

**Date:** 2026-08-07
**Repository source state used for the corrected experiment:** `80288f5e402b9b8a20a46568e00ddd494433afd3`
**Frozen Task 15 report:** `c3007f4`
**Original Semantic Exit report:** `docs/reports/semantic-memory-exit-v1.md`, recorded at `f69ba622c74089bd285571135f99660ebe687173`
**Correction evidence root:** `runs/followups/semantic-exit-v1-correction/`
**Follow-up protocol:** `sovbench/semantic-memory-exit/1-corrected-forensics`
**Dataset:** the unchanged 24-event synthetic corpus; events SHA-256 `5f5db4ca2669bd7a3795b0109ebb53a00cd841b2298910260852908e186288f`; queries SHA-256 `6403e20c880071ca57b5f6a0f4c83c89a9c44eceaf45264a468179fea93d502`; private gold commitment `3ba638c39ba3b80df11e28d4dddee4974f544a1970a146a493cff22864b0cc06`.
**Provider versions:** GBrain `15b9863d13635d173562a54f55a1d388bfcf546b` / `0.42.73.2`; Mem0 OSS `3f39fba28f7781aaf581f64a4af39d017af65835` / `2.0.17`; Hindsight `797faf7981ce9332e2ce7c922471b72b506b4065` / `0.8.6`.
**Reader:** `deepseek-v4-flash` through the existing ledgered gateway where a reader was used.
**Repository state at evidence generation:** source repository clean; ignored run artifacts retained locally; private gold was not part of the corrected public artifact.

This report supersedes the *conclusions* of the original Semantic Exit report where the errata identifies a wrong interface or recovery procedure. It does not overwrite that report or alter frozen V1 results.

## 1. Executive summary

The corrected experiment answers a narrower and more defensible question: what does each pinned product actually let a user retain, and what can a fresh same-system runtime reconstruct from that retained state?

The three original headlines required different corrections:

| Provider | Corrected result |
|---|---|
| Hindsight | The earlier version-only result used the wrong HTTP surface. Pinned `hindsight-admin export-bank` produced a real portable ZIP containing 20 documents, 20 facts, 15 observations, and configuration state. Matching `import-bank` re-embedded and rebuilt the bank without rerunning an LLM; all ten bounded recovery probes completed without errors. |
| GBrain | The earlier `No results` result came from an incomplete fresh-machine procedure. The pinned implementation treats Git/Markdown as canonical and PGLite/indexes as derived. After source registration/default routing and sync/import index rebuild, both the canonical brain and the generated `gbrain export --dir` artifact recovered 20 pages, 20 chunks, 100% embedding coverage, and all ten bounded probes. |
| Mem0 OSS | `get_all()` alone was incomplete. `get_all()+history(memory_id)` produced a machine-readable artifact for 17 currently enumerable derived memories, with history arrays for all 17. It still does not provide an export-wide raw-event stream, stable IDs after rebuild, enumerable deleted-ID tombstones, or native source-to-derived lineage. |

The strongest corrected finding is therefore not a provider leaderboard. It is a layer distinction:

1. **State ownership:** whether a user can possess meaningful state.
2. **Same-system recoverability:** whether the product can rebuild a functioning runtime.
3. **Semantic portability:** whether meaning survives independently of the original implementation.
4. **Behavioral portability:** whether another implementation could reproduce equivalent behavior.

Hindsight and GBrain pass the bounded same-system recovery tests when their actual pinned recovery contracts are followed. Mem0 can be reconstructed from current derived memories without an LLM, but its documented OSS surface does not expose the complete state/history needed for lossless semantic recovery. None of these observations makes a product universally best.

**Recommendation:** publish a corrected, evidence-bounded V1 and stop the broad roadmap. Use a layered architecture for future personal/project and enterprise memory: an independently controlled canonical event/provenance ledger, plus product-specific derived indexes and retrieval views.

## 2. Frozen V1 context

Task 15 remains frozen at `c3007f4`. Its controlled and native benchmark tables are not recomputed or merged with this report. The original Semantic Exit experiment at `f69ba622c74089bd285571135f99660ebe687173` is preserved as the first record. This document is a forensic correction, not a replacement V1 leaderboard.

Relevant frozen context includes native Mem0 Recall@1 falling from controlled `0.600` to native `0.418`, while native Hindsight changed from `0.709` to `0.727`. Those values explain why controlled and product-native tracks must remain separate; they are not portability scores.

The local Ollama GBrain embedding experiment is also not revisited here. Its preregistered DEV quality gate failed, so its hidden TEST run was correctly not performed. The same local model was used only as recovery infrastructure in this pass; no new embedding-quality claim is made.

## 3. Exact research question

> If a user leaves a memory product and retains only the state that the product legitimately lets the user keep, how much trustworthy memory meaning survives after the original application state is gone?

The experiment is not a general recall benchmark, migration matrix, or interoperability framework. It measures documented/native exit state, same-system reconstruction, and semantic field survival on a small, deliberately adversarial corpus.

## 4. Errata summary

The full audit trail is in `docs/reports/semantic-memory-exit-v1-errata.md`.

### Hindsight

**Original conclusion:** the tested export returned only `{"version":"1"}` and did not recover useful state.
**Corrected conclusion:** this was a harness/interface error. The pinned v0.8.6 source includes `hindsight-admin export-bank` and `import-bank`. The correct archive includes documents, facts, observations, configuration, and related native state; it excludes embeddings, which are regenerated. Same-system recovery succeeded.

### GBrain

**Original conclusion:** 20 human-readable pages could be imported but all ten recovery searches returned `No results`.
**Corrected conclusion:** this was a recovery-configuration error. The pinned source distinguishes a canonical Git/Markdown brain from derived PGLite/index state. Registering the source, establishing default routing, and running the documented sync/import/reindex sequence restored retrieval through both tested paths.

### Mem0

**Original conclusion:** `get_all()` exposed 17 derived memories but lost raw source semantics.
**Corrected conclusion:** directionally retained but incomplete. The maximal documented OSS artifact adds `history(memory_id)` for every memory returned by `get_all()`. It preserves history for those enumerable IDs, but not export-wide lineage, deleted-ID enumeration, raw events, or stable IDs after re-add. The initial recovery's unsupported `reference_date` argument was also removed and is recorded as a harness correction.

## 5. Systems and configurations

| System | Pinned source | Exit surface tested | Persistence/recovery | LLM during population | LLM during recovery |
|---|---|---|---|---|---|
| GBrain | `15b9863d...`, `0.42.73.2` | A1 canonical Git/Markdown brain; A2 `gbrain export --dir` Markdown | PGLite and indexes derived; source registration plus sync/import/reindex required | Existing native adapter path; recovery pass did not add calls | No |
| Mem0 OSS | `3f39fba...`, `2.0.17` | `Memory.get_all()` plus `Memory.history(memory_id)` | Chroma-derived current memories plus SQLite history; recovery re-added current memory text | DeepSeek through gateway during native population | No; `infer=False` re-add |
| Hindsight | `797faf7...`, `0.8.6` | `hindsight-admin export-bank`, with matching `import-bank` | PostgreSQL/pgvector bank; facts are re-embedded and links/indexes rebuilt | DeepSeek through gateway during native population | No; import re-embeds and rebuilds |

No provider was upgraded or patched. No hosted embedding fallback, Gemini, new provider, cross-system conversion, enterprise corpus, STATE-Bench integration, or large-scale experiment was run.

## 6. Dataset and protocol

The original 24-event corpus and private gold were reused unchanged. The corpus includes stable facts, preferences and changes, historical and superseded facts, corrections, temporary facts, source/ingestion-time differences, explicit user statements, model inference, untrusted and authoritative sources, conflicting authority, private and shared scopes, explicit deletion, do-not-store instructions, multi-fact events, provenance chains, and ambiguity.

There were ten bounded recovery queries. Provider-native behavior was not normalized away. Private gold remained unavailable to providers and was not copied into the primary exit artifacts. The original runtime was removed after the retained artifact was hashed; derived indexes, caches, and provider working directories were not treated as user exports.

Fidelity classifications are:

- **PRESERVED** — represented with equivalent meaning in the tested artifact.
- **TRANSFORMED BUT EQUIVALENT** — represented in a different shape without observed semantic change.
- **DEGRADED** — some meaning or lineage survives but not completely.
- **LOST** — the artifact contains no recoverable representation for the case.
- **UNSUPPORTED** — the product/export contract does not expose the property.
- **NOT OBSERVABLE** — this experiment cannot determine it from the documented/native surface.

These are field-level observations, not a composite score.

## 7. Corrected provider evidence

### 7.1 Hindsight whole-bank export/import

Pinned source inspection found:

- `hindsight-admin export-bank --bank ... --output ...` creates a portable ZIP.
- The archive contains bank rows, documents, facts, observations, mental models, directives, webhooks, and a manifest. Operational `audit_log` and `llm_requests` history is optional and was not included in the primary artifact.
- Embeddings/search vectors are omitted from the archive.
- `hindsight-admin import-bank --archive ... --target-bank ...` re-embeds facts with the target embedding model and rebuilds links/entities/indexes.
- Import does not rerun LLM extraction.
- Entities and links are regenerated; the archive is not a byte-for-byte database copy.

The adapter-independent smoke test inserted one distinctive marker, exported it, destroyed the bank/runtime, recreated the pinned runtime, imported the ZIP, and retrieved the marker. The corrected 24-event run then produced:

| Measure | Result |
|---|---:|
| Documents | 20 |
| Facts | 20 |
| Observations | 15 |
| Mental models | 0 in this corpus |
| Directives/webhooks | 0 in this corpus |
| Operational history | not included; default export behavior |
| Archive SHA-256 | `70bbe4f28ccd1cf622a7bb1e8d720975d7f9b85c1f45b33ff3c4c75da6db8e` |
| Post-import query errors | 0/10 |
| LLM calls during import | 0 |

This is a real same-system bank transfer, not the version-only HTTP response used in the original experiment. It is still not a complete raw event ledger: deleted events are not retained in the primary artifact, operational history was not included, and the native schema does not expose every gold property as an explicit first-class field.

### 7.2 GBrain canonical recovery and generated export recovery

Pinned source inspection found:

- Git/Markdown pages are the canonical source of truth in the pinned architecture.
- PGLite pages/chunks, embeddings, and search indexes are derived state.
- `gbrain export --dir` writes a Markdown artifact from database pages; that artifact is distinct from the original configured source repository.
- `gbrain import` requires source resolution and embedding configuration unless embeddings are explicitly skipped.
- A fresh runtime must register the source, establish routing/default source, and run sync or the matching import/reindex path.

The corrected independent smoke test used three distinctive pages. Both a canonical Git/Markdown recovery and a generated export/import recovery returned exact keyword results and semantic results after index rebuilding.

The 24-event correction produced:

| Measure | A1 canonical Git/Markdown | A2 generated `export --dir` |
|---|---:|---:|
| Human-readable pages | 20 | 20 |
| Pages/chunks after rebuild | 20/20 | 20/20 |
| Embedding coverage | 100% | 100% |
| Source registered/routed | yes | yes |
| Bounded recovery queries without error | 10/10 | 10/10 |
| LLM calls during recovery | 0 | 0 |
| Artifact SHA-256 | `6a32eb275b05c055c871cb56448c66cf76653222cab964a2a91636275249a0bf` | `bddd051ac46d78c3ed09a36f1de02d63188486b98e9d9661a7b6194390bfa277` |

The previous `No results` finding is therefore retracted as a provider limitation. It remains a useful forensic lesson: a copied Markdown directory is not enough unless the pinned product's source registration and derived-index contract are also restored.

### 7.3 Mem0 maximal documented OSS surface

Pinned source inspection found:

- `Memory.get_all()` enumerates current vector-store memories.
- `Memory.history(memory_id)` returns SQLite history for a known memory ID.
- Updates and deletes write history rows, but deleted memories are removed from the current vector store and their IDs are not enumerated by `get_all()`.
- No OSS `export`/`import` implementation beyond these surfaces was found in the pinned package.
- Hosted Mem0 platform export features are not attributed to the OSS SDK.
- The pinned OSS SDK does not support `reference_date` in `search`; the corrected recovery did not pass it.

The corrected native-only artifact contains 17 current memories, each with a history array, with zero history collection errors. The observed history rows were `ADD` rows. Recovery re-added the 17 memory texts with `infer=False`, did not call an LLM, and produced new memory IDs. History was not recreated and retrieval was executed without unsupported as-of parameters.

| Measure | Result |
|---|---:|
| Current memories from `get_all()` | 17 |
| Memories with collected history | 17/17 |
| History collection errors | 0 |
| History rows observed for current IDs | ADD rows in this run |
| Raw source-event export | no |
| Export-wide deleted-ID enumeration | no |
| LLM required for current-memory re-add | no |
| Stable IDs after recovery | no |
| Artifact SHA-256 | `fe0d1ac5476b8aecebebcd19ffbd9ea0cd51058afb9251cb66995b0d2ffa1522` |

`history()` improves the maximal documented artifact, but it does not convert current derived-memory enumeration into a complete source-event export contract.

## 8. Four portability layers

| Layer | GBrain | Hindsight | Mem0 OSS |
|---|---|---|---|
| A. State ownership | Strong for canonical Git/Markdown pages; generated export is a separate artifact | Strong for the user-accessible whole-bank ZIP when the admin mechanism is available | Moderate for current derived memories; no complete OSS export contract |
| B. Same-system recoverability | Passed both corrected bounded paths after source registration and index rebuild | Passed matching admin export/import; re-embedding/index rebuild required | Current derived memories can be re-added without an LLM; histories and IDs are not fully reconstructed |
| C. Semantic portability | Human-readable pages retain source text and adapter metadata, but product semantics are not a neutral interchange schema | Documents/facts/observations transfer, but deleted events, optional operational history, and some semantic relations are not complete | Derived text and some metadata transfer; raw source, lineage, intervals, and tombstones are incomplete or not observable |
| D. Behavioral portability | Same product behavior recovered in the tested pinned sequence; cross-product equivalence not tested | Same product bank behavior recovered; cross-product equivalence not tested | Approximate current-memory behavior can be rebuilt; exact historical behavior cannot be claimed |

Passing layer B does not imply passing layers C or D.

## 9. Corrected semantic fidelity matrix

The matrix reports the primary Category A artifact for each provider. “Adapter-mediated” means the field was supplied or interpreted by the benchmark adapter and is not evidence of a native governance guarantee.

| Property | GBrain canonical / export | Hindsight whole-bank | Mem0 OSS `get_all()+history` |
|---|---|---|---|
| Raw source event | Preserved as Markdown text, with adapter caveat | Preserved for retained documents; deleted/nonretained events absent | Lost as an export-wide source stream |
| Derived memories | Preserved/rebuildable as pages/indexes | Preserved facts and observations; vectors regenerated | Preserved current derived memory text |
| Original source identity | Adapter frontmatter where present | Adapter metadata where present; native lineage not proven | Adapter metadata where present; native lineage not observable |
| Provenance | Adapter-mediated; not a native guarantee | Adapter-mediated metadata survives retained rows | Not observable as a native lineage contract |
| Authority | Adapter-mediated frontmatter | Adapter metadata survives retained rows | Adapter metadata only where retained |
| Explicit user vs model-derived | Representable in tested frontmatter only where supplied | Representable in retained metadata/fact shape; not independently guaranteed | Degraded; derived text is not a reliable source-type record |
| Creation/mention/source timestamps | Frontmatter and file state where supplied | Transformed into document/fact time fields; not every source timestamp is first-class | Native created/updated timestamps; source/event time not guaranteed |
| `valid_from` | Adapter field where present | Partly transformed; otherwise unsupported/not observable | Lost |
| `valid_to` / expiry | Adapter field where present | Partly transformed; otherwise unsupported/not observable | Lost or only native expiration when explicitly present |
| Supersession/history | Frontmatter/source history can be retained, but index behavior is product-specific | Not a complete native supersession contract; some relations/observations may survive | History only for known current IDs; source supersession relation lost |
| Principal/scope | Adapter frontmatter and source routing | Adapter metadata and bank scope; native governance not proven | `user_id`/metadata for enumerated memories; no universal governance claim |
| Deletion/tombstones | Git/file history can show deletion if retained, but no portable product tombstone contract tested | Deleted source events absent from primary archive; tombstone preservation not observable | Deleted IDs are not enumerable through `get_all()`; tombstone export not available |
| Human readability | Strong Markdown | Readable JSON/ZIP | Readable JSON, not a narrative export |
| Machine readability | Strong Markdown/frontmatter plus product parser | Strong structured ZIP/JSON | Strong JSON plus history arrays |
| Index rebuildability | Passed; derived indexes rebuilt | Passed; embeddings/links/indexes rebuilt | Current-memory re-add passed; historical/index equivalence not proved |
| LLM-free restore | Passed | Passed | Passed for current memory text; not full semantic recovery |
| Behavioral recovery | Passed both bounded paths | Passed bounded path | Partial current-memory behavior only |

## 10. Native state versus adapter and runner properties

The corrected findings must not attribute benchmark behavior to products merely because the harness made it visible.

| Property | Evidence source in this study |
|---|---|
| Canonical GBrain page content | Product-native Git/Markdown workflow, with adapter-created test content/frontmatter |
| GBrain source routing and index rebuild | Product CLI contract, exercised by the correction |
| Hindsight documents/facts/observations in bank archive | Product-native admin export/import |
| Hindsight adapter event IDs, principal, source, authority and scope metadata | Adapter-supplied document metadata; not native governance proof |
| Mem0 current memories | Product-native `get_all()` |
| Mem0 per-memory history | Product-native `history(memory_id)` for IDs returned by `get_all()` |
| Mem0 raw source-event registry | Benchmark adapter only; excluded from primary Category A artifact |
| Future/as-of filtering in V1 controlled track | Benchmark runner/adapter; not claimed as native Mem0 OSS capability |
| Reader answer quality in V1 | Common DeepSeek reader and prompt; not used as a portability guarantee |
| Private gold and classification | Benchmark runner, inaccessible to providers |

This attribution boundary is one of the most important results of the overall project.

## 11. Same-system recovery comparison

### Hindsight

Pre-exit population produced the native bank. The primary exit ZIP was hashed, the original runtime was removed, a fresh pinned runtime was started, and the matching bank import was executed. Import reported 20 documents, 20 facts, and 15 observations; embeddings were regenerated and indexes rebuilt; no LLM extraction occurred. Ten post-import bounded probes returned without query errors.

### GBrain

The primary A1 path retained the canonical Git/Markdown brain and recreated the fresh runtime's source registration. The A2 path separately retained the generated export and registered it as a source before import/reindex. Both resulted in 20 pages, 20 chunks, 100% embedding coverage, and ten error-free bounded probes. The old failure occurred before the correct source/index boundary was reached.

### Mem0

The primary artifact retained only the documented OSS result of `get_all()` plus history for each enumerated ID. A fresh runtime re-added the 17 current derived memories without inference. IDs changed, histories were not recreated, and exact retrieval equivalence was not claimed. The pinned SDK has no as-of search parameter, so temporal behavior after recovery is not observable through that interface.

## 12. Failure and correction analysis

| Observation | Category | Disposition |
|---|---|---|
| Hindsight version-only HTTP response | Harness/interface failure | Corrected by using pinned admin whole-bank export |
| Hindsight first matching import attempt | Infrastructure/procedure issue | Superseded by adapter-independent smoke and corrected run |
| GBrain `No results` after copied Markdown | Recovery configuration failure | Corrected with source registration, routing, sync/import and index rebuild |
| Mem0 initial `reference_date` errors | Harness/API misuse | Corrected; unsupported parameter removed |
| Mem0 missing deleted IDs in `get_all()` | Native OSS surface limitation | Retained as a documented limitation of the maximal tested artifact |
| Hindsight missing deleted source events from archive | Export semantics/native limitation for this artifact | Retained; do not call the archive a complete append-only ledger |
| Metadata surviving in artifacts | Adapter-mediated | Retained only with attribution caveat |

## 13. Cross-system migration

No cross-system migration was implemented. After correcting the native interfaces, a cross-system pair would not isolate a new question without adding a mapping contract and another source of adapter-defined semantics. This was intentionally stopped to preserve the narrow scope.

The evidence supports a follow-up question about semantic migration, but it does not answer it. An existing interchange representation should be tested before claiming that migration is unsolved. Relevant current work includes the [W3C AI Agent Memory Interoperability Community Group](https://www.w3.org/groups/cg/ai-agent-memory-interop/), the [AIMEM Bundle Internet-Draft](https://www.ietf.org/archive/id/draft-vu-aimem-bundle-00.html), and the [ApertoMemory Internet-Draft](https://www.ietf.org/ietf-ftp/internet-drafts/draft-ferro-apertomemory-02.html). Internet-Drafts are works in progress, not adopted standards.

## 14. Limitations

- One small synthetic corpus, one population replicate per provider, and one machine.
- Native extraction and consolidation depend on the pinned DeepSeek gateway configuration.
- Recovery probes were bounded and are not a new recall leaderboard.
- GBrain recovery used the local embedding service but did not test its failed DEV quality gate again.
- Hindsight operational history was not included in the primary export; optional history could change audit-state coverage without changing the result that the archive is not a raw event ledger.
- Mem0 history was collected only for IDs returned by `get_all()`; the documented interface does not enumerate deleted IDs for an export-wide history walk.
- Adapter-supplied metadata makes some semantic fields observable, but does not prove native product governance.
- No second independent machine, cross-system migration, scale test, or alternate reader was run.
- The study reports exact pinned versions, not current product behavior generally.

These limits prevent a universal provider ranking and prevent the stronger claim that portable AI memory is generally solved or generally unsolved.

## 15. Personal/project-memory recommendation

If the priority is to change AI agents or memory software later without losing trustworthy accumulated memory, choose a **layered approach**, not one provider as the sole source of truth:

1. Keep a user-controlled canonical ledger containing raw source text, event and ingestion times, validity intervals, authority, provenance, principal/scope, explicit-versus-derived status, supersession, and deletion/tombstone state.
2. Use the memory product as a rebuildable derived view and retrieval index.
3. Keep export receipts, hashes, restore manifests, and periodic fresh-environment recovery drills.

If a product layer must be selected for a narrow purpose: GBrain is strongest for human-readable canonical state in this test; Hindsight is strongest for a documented product-native whole-bank same-system transfer; Mem0 OSS is convenient for current derived-memory enumeration but weakest as a standalone semantic exit surface. This is not a “winner” declaration. The layered architecture is the conclusion.

## 16. Enterprise-memory recommendation

Enterprise memory should not rely on a provider database as the only durable record. Vendor independence requires an independently controlled state layer with:

- provenance and source-to-derived lineage;
- authority and conflict resolution;
- valid-from/valid-to and historical state;
- principal, group, and policy scopes;
- deletion requests, tombstones, and verifiable erasure behavior;
- audit records and export hashes;
- disaster recovery that reconstructs a fresh runtime without silently rerunning an LLM;
- disposable, rebuildable provider indexes.

Hindsight's whole-bank export and GBrain's canonical repository can be useful recovery mechanisms, but neither observation removes the need to preserve a semantic ledger separately. Mem0 OSS's documented current-memory/history surface is not sufficient alone for enterprise audit and portability requirements.

## 17. Final recommendation

**Publish the corrected V1 evidence and stop the broad Tasks 16–20 roadmap.** The project now has a stronger, more honest result because two negative headlines were retracted when the correct product interfaces were used. A further provider run is not scientifically essential to this correction. Before any submission, perform human editorial review, cite current prior work, publish reproducibility material without private gold, and have an independent reviewer inspect the attribution boundary.

## 18. Reproduction information

The corrected evidence was generated from the unchanged corpus and pinned sources. The run scripts are additive and are not required to alter frozen V1.

Relative commands used for the forensic pass were equivalent to:

```powershell
python scripts/run_semantic_exit_corrections.py --provider hindsight
python scripts/run_semantic_exit_corrections.py --provider mem0
python scripts/finalize_gbrain_correction.py --attempt runs/followups/semantic-exit-v1-correction/attempt-20260807T063919Z
python scripts/finalize_mem0_recovery.py --observation runs/followups/semantic-exit-v1-correction/attempt-20260807T065850Z/mem0/observation.json
python scripts/refine_hindsight_fidelity.py --observation runs/followups/semantic-exit-v1-correction/attempt-20260807T065643Z/hindsight/observation.json
```

The actual ignored run root is `runs/followups/semantic-exit-v1-correction/`; the report intentionally omits machine-specific absolute paths. Hindsight import used the matching pinned `hindsight-admin export-bank`/`import-bank` commands. GBrain recovery used pinned `sources add`, `sources default`, `sync`, `import`, and index rebuild operations. Mem0 recovery used only the primary JSON artifact, `get_all()` output, and collected `history(memory_id)` data.

Additional API cost for the corrected successful Hindsight and Mem0 populations was approximately **USD 0.065622**: Hindsight `0.036365`, Mem0 `0.029257`. GBrain recovery used no DeepSeek calls. The failed Python-environment attempt incurred no provider API cost.

## Appendix A — Evidence identifiers

- Hindsight corrected run: `attempt-20260807T065643Z`.
- GBrain corrected recovery run: `attempt-20260807T063919Z`.
- Mem0 corrected maximal OSS run: `attempt-20260807T065850Z`.
- Hindsight archive SHA-256: `70bbe4f28ccd1cf622a7bb1e8d720975d7f9b85c1f45b33ff3c4c75da6db8e`.
- GBrain A1 canonical SHA-256: `6a32eb275b05c055c871cb56448c66cf76653222cab964a2a91636275249a0bf`.
- GBrain A2 generated export SHA-256: `bddd051ac46d78c3ed09a36f1de02d63188486b98e9d9661a7b6194390bfa277`.
- Mem0 maximal OSS artifact SHA-256: `fe0d1ac5476b8aecebebcd19ffbd9ea0cd51058afb9251cb66995b0d2ffa1522`.

## Appendix B — No-go scope confirmation

This correction did not add Graphiti, Cognee, MIND-Mem, enterprise data, STATE-Bench, a migration matrix, a new reader model, Gemini embeddings, or a generalized migration framework. It did not modify or merge the frozen Task 15 results.
