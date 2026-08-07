# Memory Sovereignty Benchmark — Publication Readiness Review

**Date:** 2026-08-07
**Evidence basis:** frozen Task 15 at `c3007f4`; original Semantic Exit record at `f69ba622c74089bd285571135f99660ebe687173`; corrected forensic evidence generated from source state `80288f5e402b9b8a20a46568e00ddd494433afd3`.
**Reports:** `docs/reports/semantic-memory-exit-v1.md`, `docs/reports/semantic-memory-exit-v1-errata.md`, and `docs/reports/semantic-memory-exit-v1-corrected.md`.

This is a publication-readiness assessment, not an article draft. It deliberately treats corrected negative findings and retracted conclusions as research evidence rather than trying to preserve a novelty narrative.

## Executive assessment

The work supports a credible empirical engineering contribution if framed as an evidence and attribution study:

> Memory evaluation can produce misleading governance conclusions when a normalized adapter, benchmark runner, or reader prompt supplies the very provenance, authority, scope, temporal, or deletion semantics that are later attributed to the memory product.

The corrected exit pass strengthens this framing because it retracts two apparent product failures caused by wrong recovery procedures:

- Hindsight's original version-only HTTP result was not its pinned whole-bank export.
- GBrain's original `No results` recovery was not a valid reconstruction of the pinned source/index contract.

The third result remains a product-surface observation rather than a universal verdict:

- Mem0 OSS's maximal documented `get_all()+history()` artifact preserves current derived memories and history for enumerable IDs, but not an export-wide raw-event, lineage, or deleted-ID tombstone contract.

The resulting contribution is **incremental but useful**, with the capability-attribution problem the strongest and most differentiated part. A defensible paper should not claim that AI memory portability is universally unsolved, that any provider is “bad,” or that the benchmark establishes a universal ranking.

## 1. Candidate contribution A — controlled versus native evaluation

### Exact supportable claim

Testing a normalized storage/retrieval interface can produce materially different observations from testing the complete native memory-formation pipeline. Therefore a benchmark should publish controlled and product-native results separately and identify which properties are supplied by the adapter, runner, reader, or product.

### Evidence

The frozen Task 15 run recorded native Mem0 Recall@1 falling from controlled `0.600` to native `0.418`, while native Hindsight changed from `0.709` to `0.727`. The native track also exposed extraction, consolidation, timing, lifecycle, and reproducibility behavior that a controlled track intentionally removed. The frozen harness-attribution table identified as-of filtering, scope filtering, provenance, and authority interpretation as adapter/runner/reader-mediated in the controlled path.

### Threats to validity

- Only the pinned providers and one common reader were tested.
- Differences may depend on adapter quality, prompts, embeddings, native model configuration, and the small synthetic corpus.
- The result is not evidence that native tracks are always more realistic or controlled tracks are always invalid.
- One native replicate per provider limits variance estimates.

### Prior work

LongMemEval, LoCoMo, BEAM, and AMB motivate memory-task and agent-level evaluation, but this project measures provider lifecycle and governance boundaries at the memory-layer interface. STATE-Bench is stronger for downstream stateful task completion and should be reused if a later agent-task validation is needed. AMB already provides an ingest/retrieve/generate/judge pattern and warns that model and prompt choices move scores. The project should reuse these ideas rather than present the pipeline structure as novel.

### Assessment

**INCREMENTAL BUT USEFUL.** The contribution is an evaluation protocol and evidence discipline, not a new memory algorithm.

### Strongest framing

“Controlled and native memory evaluation answer different questions: storage/retrieval capability versus end-to-end product behavior.”

### Claims to avoid

- “Native evaluation is the only valid benchmark.”
- “Our controlled score predicts product behavior.”
- “This is the first benchmark to compare controlled and native memory.”

## 2. Candidate contribution B — capability attribution

### Exact supportable claim

Memory benchmarks can attribute governance capabilities to products incorrectly when adapters, runners, or reader prompts enforce as-of filtering, provenance, authority, scope, deletion mapping, or future-information exclusion. A benchmark should publish a capability-attribution matrix for every reported property.

### Evidence

The frozen Task 15 harness-vs-product section explicitly separated native product behavior from adapter, runner, and reader contributions. The corrected exit pass reinforced this boundary:

- Hindsight archives retained source, authority, and scope metadata in this run partly because the benchmark adapter supplied those fields.
- GBrain Markdown frontmatter retained fields selected by the adapter; successful reindexing did not make those fields native governance guarantees.
- Mem0 `get_all()+history()` exposed current memories and per-ID history, but the adapter's private source-event registry was excluded from the primary exit artifact.
- The initial GBrain and Hindsight negative findings were corrected only after tracing the earliest failed interface boundary.

### Threats to validity

- The benchmark itself controls the interface and can create attribution artifacts.
- “Native” is not a single universal category: a product may have product-native state plus application-provided metadata.
- More providers and independent auditors would strengthen generality, but are outside this completed scope.

### Prior work

MemSecBench, GateMem, AuthMem-Bench, and SovereignPA-Bench motivate security, authority, and sovereignty dimensions. Their existence means the underlying concerns are not new. The narrower contribution is the explicit accounting of *who implemented each observed guarantee* during a provider comparison.

### Assessment

**UNDEREXPLORED / INCREMENTAL BUT USEFUL.** This is the strongest candidate contribution, but “first” language requires a systematic literature review that this repository does not claim to have completed.

### Strongest framing

“Do not call a benchmark-enforced property a memory-product capability.”

### Claims to avoid

- “Existing benchmarks never distinguish harness from product.”
- “No memory product supports provenance.”
- “Adapters are invalid.”

## 3. Candidate contribution C — canonical versus derived memory state

### Exact supportable claim

A recovery drill must identify the product's canonical state and treat indexes, embeddings, caches, and query routing as derived state. Copying files that are readable is not enough; the source-registration and rebuild contract must be tested.

### Evidence

Pinned GBrain source inspection and the corrected smoke test demonstrated a canonical Git/Markdown brain plus derived PGLite/index state. Hindsight's pinned import similarly re-embeds and rebuilds links/indexes rather than copying vectors. Mem0 separates current derived vector memories from SQLite history. The correction pass found that invalid recovery sequencing can mimic data loss.

### Prior work

Canonical-versus-indexed state is established in databases, search systems, Git-backed applications, and memory architectures. The project should cite and reuse that body of work; it should not claim this architecture as novel.

### Assessment

**ALREADY WELL ESTABLISHED**, with an **INCREMENTAL BUT USEFUL** empirical warning for AI memory products.

### Strongest framing

“A memory export must declare its canonical state and rebuild procedure, not only produce files.”

### Claims to avoid

- “GBrain invented canonical memory state.”
- “Every Markdown export is a complete backup.”

## 4. Candidate contribution D — semantic portability

### Exact supportable claim

Documented exit artifacts differ in whether they preserve raw source text, derived memories, provenance, authority, temporal validity, supersession, scopes, deletion state, and rebuildability. Same-system restore is evidence about disaster recovery, not proof of semantic or behavioral portability.

### Evidence

The corrected pass found:

- Hindsight's real whole-bank archive restored a working pinned bank and retained documents, facts, and observations, but did not represent every gold property as a complete event-ledger schema.
- GBrain's canonical and generated Markdown paths recovered behavior after correct source registration and indexing; readable state and rebuild procedure were jointly necessary.
- Mem0's maximal documented OSS artifact preserved current derived memories and history for known current IDs but lacked export-wide raw source, deleted-ID enumeration, stable IDs after re-add, and native lineage.

### Prior work and standards

The [W3C AI Agent Memory Interoperability Community Group](https://www.w3.org/groups/cg/ai-agent-memory-interop/) is explicitly working on portable AI-agent memory and identifies canonical metadata, sharing, audit, and erasure semantics as in scope. The [AIMEM Bundle Internet-Draft](https://www.ietf.org/archive/id/draft-vu-aimem-bundle-00.html) specifies a vendor-neutral bundle format. The [ApertoMemory Internet-Draft](https://www.ietf.org/ietf-ftp/internet-drafts/draft-ferro-apertomemory-02.html) addresses signed, encrypted portable memory objects and custody records. These works make a broad “portable memory is unsolved” claim indefensible without testing them.

### Threats to validity

- Only one small corpus and one replicate per provider.
- No cross-system migration was executed.
- The corpus is synthetic, so real product schemas may expose different fields.
- Native metadata and adapter metadata are difficult to separate completely.
- No claim is made about current versions beyond the pinned commits.

### Assessment

**INCREMENTAL BUT USEFUL; not sufficient for a universal portability result.** The strongest result is a taxonomy of portability layers and an empirical warning about conflating them.

### Strongest framing

“A complete exit claim must state which portability layer it satisfies and which semantic fields it preserves.”

### Claims to avoid

- “No existing interchange format can solve these losses.”
- “Same-system restore proves vendor independence.”
- “Hindsight, GBrain, or Mem0 is universally sovereign.”

## 5. What survives without a recall leaderboard

The research remains useful without Recall@1/5/10 tables because its strongest observations are about experimental validity and state contracts:

1. **Capability attribution is measurable.** A report can state whether a property came from native state, an adapter, the runner, or the reader.
2. **Wrong interfaces create false research conclusions.** Hindsight and GBrain both demonstrate that forensic source inspection and adapter-independent smoke tests are necessary before assigning a negative result to a provider.
3. **State ownership and behavioral recovery are separable.** GBrain's readable source required registration and index rebuilding; Hindsight's archive required re-embedding; Mem0's derived memories could be re-added but did not reconstruct history.
4. **Semantic exit needs explicit fields.** Raw source, source identity, authority, validity, supersession, scope, and deletion cannot be assumed to survive because text or vectors survived.
5. **A layered architecture is empirically justified.** Provider indexes are useful, but a user/organization-owned source ledger reduces dependence on a vendor-specific derived representation.

These findings are modest, falsifiable, and useful to engineers even if all provider retrieval scores are removed.

## 6. Venue readiness

### arXiv

**Recommendation: NOT YET.** The corrected evidence is sufficient for a defensible preprint *after* the public reproduction package, citations, and independent review are prepared. The current repository reports are research records, not a submission-ready manuscript. No additional provider experiment is scientifically required by this review, but the preprint should include:

- a compact research question and threat-to-validity section;
- the controlled/native attribution table;
- explicit errata and correction history;
- public code and redacted manifests;
- private-gold evaluation protocol without revealing answers;
- exact pinned versions and a fresh-environment reproduction check;
- a systematic related-work pass, especially against interoperability proposals.

The arXiv category should be chosen only after reading the current taxonomy and matching the final manuscript; `cs.SE` and `cs.AI` are plausible, not commitments. See the [arXiv category taxonomy](https://arxiv.org/category_taxonomy) and [submission guidance](https://info.arxiv.org/help/submit.html).

### IEEE Software

**Recommendation: YES, after a practitioner rewrite and independent review.** IEEE Software is a better fit for actionable design lessons than a raw benchmark dump: controlled versus native evaluation, canonical versus derived state, export drills, and capability attribution are useful to senior engineers and architects. The submission should follow the publication's current aims and author instructions through the [IEEE Author Center](https://ieeeauthorcenter.ieee.org/) and the [IEEE magazine submission process](https://magazines.ieeeauthorcenter.ieee.org/submit-your-article-for-peer-review/the-ieee-article-submission-process/).

The article must present the retractions plainly and avoid a vendor ranking. It should be a lessons-learned architecture article supported by measured evidence, not a claim of a new benchmark state of the art.

### InfoQ

**Recommendation: YES, after a tight practitioner rewrite.** InfoQ's official author guidance targets senior engineers, architects, and team leads; it asks for timely, educational, practical, technically accurate, marketing-free material. That matches a focused article on “how to test AI memory without attributing adapter guarantees to the product,” not a long academic report. See [InfoQ author guidelines](https://www.infoq.com/guidelines/).

The article should contain concrete takeaways: run controlled and native tracks, record canonical state, perform a clean-room restore, classify semantic fields, and publish a capability-attribution matrix. InfoQ also requires human accountability and disclosure of generative-AI assistance; those obligations must be handled by the author in any future submission.

### W3C AI Agent Memory Interoperability Community Group

**Recommendation: YES, as a contribution to the existing group, not a competing standard.** The corrected findings translate into concrete requirements and test cases:

- distinguish raw source, derived memory, and observations;
- represent explicit user statements separately from model-derived claims;
- carry source timestamps, validity intervals, supersession, authority, and provenance;
- carry principal/scope and deletion/tombstone state;
- declare canonical state and rebuild requirements;
- define whether an export is a user-intended transfer or disaster-recovery copy;
- describe whether import is LLM-free and whether it is deterministic.

The W3C group already states portability, canonical metadata, sharing, audit, and erasure as in scope. The appropriate contribution is a short evidence-backed requirements note or test-case proposal, not a new protocol from this repository.

### IETF

**Recommendation: NOT YET.** Current work already includes multiple individual Internet-Drafts with overlapping memory portability and governance surfaces, including [AIMEM Bundle](https://www.ietf.org/archive/id/draft-vu-aimem-bundle-00.html), [ApertoMemory](https://www.ietf.org/ietf-ftp/internet-drafts/draft-ferro-apertomemory-02.html), and [SAIHM](https://datatracker.ietf.org/doc/draft-saihm-memory-protocol/). An Internet-Draft is not an IETF standard and the corrected experiment does not yet demonstrate a protocol gap that merits a competing draft.

If the work is shared with IETF participants, contribute empirical requirements and implementation feedback to existing efforts first. Do not submit a new draft merely because the benchmark can list missing properties.

## 7. Publication package requirements

Before any submission, the author should:

1. Keep the original report and errata in the repository.
2. Publish redacted code, manifests, version pins, and reproduction commands.
3. Keep private gold out of Git and document how an external reviewer can verify the commitment without seeing answers.
4. Include a table separating product-native, adapter, runner, and reader properties.
5. Include the Hindsight and GBrain corrections rather than hiding them.
6. Avoid using aggregate scores as the thesis.
7. Cite prior benchmarks and interoperability work directly.
8. Obtain one independent technical review of the corrected report and the reproduction path.

The independent review is a publication-quality safeguard, not an additional benchmark phase.

## 8. Decision on more experiments

No additional experiment is scientifically essential for this correction pass. A future semantic interoperability experiment could test one existing interchange representation against the same private gold, but it must be separately approved. Do not begin it automatically.

The broad Tasks 16–20 roadmap remains stopped. No new provider, larger corpus, migration framework, or downstream agent benchmark is recommended here.

## 9. Final assessment

The project is publishable as a careful empirical engineering study if it stays modest. The strongest defensible contribution is the combination of:

- controlled-versus-native separation;
- explicit capability attribution;
- forensic validation of the provider's actual recovery contract;
- a four-layer portability taxonomy;
- a layered design recommendation grounded in observed losses and corrected failures.

That is enough for a useful portfolio-quality research artifact and a plausible practitioner submission. It is not evidence for a universal memory-product ranking or a new general memory-interchange standard.
