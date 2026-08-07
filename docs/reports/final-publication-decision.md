# Final Publication Decision

**Date:** 2026-08-07
**Basis:** Capability Attribution Ablation v1 (`docs/reports/capability-attribution-v1.md`), frozen Task 15 evidence (`c3007f4`), corrected Semantic Exit (`semantic-memory-exit-v1-corrected.md`), and errata (`semantic-memory-exit-v1-errata.md`).

## arXiv

**Status: READY AFTER INDEPENDENT REVIEW**

The strongest defensible thesis: some measured memory-governance capabilities
depend materially on benchmark-supplied semantics, so memory benchmarks must
attribute capabilities to product, adapter, runner, reader, and scorer layers.

Evidence: temporal filtering is material by every preregistered gate
(GBrain +0.463, Mem0 +0.472, Holm p 3.1e-05 and 3.0e-05, future leakage to
zero); principal isolation for GBrain and Hindsight moves cross-principal
evidence and unauthorized answers from clearly nonzero to zero; provenance
source identification is 0.000 without benchmark metadata and 0.889 to 1.000
with it across all three providers.

Research questions for a paper:

1. How much measured temporal/current-state correctness is supplied by the
   benchmark runner rather than the memory product?
2. Which governance properties survive removal of benchmark metadata and
   instructions?
3. When do benchmark results report a capability the product does not natively
   enforce?
4. What does a layer-attribution matrix add over aggregate governance scores?

Likely categories: cs.AI (memory systems and evaluation), cs.SE (empirical
methodology).

Required before submission:

- replicate the temporal and scope ablations on a second corpus or at least
  one more provider to widen the evidence base;
- expand the provenance query set so the metadata dependency clears a
  statistical gate rather than remaining directional;
- independent reproduction by a second lab;
- a public redaction pass over prompts, adapter code, and results so the
  reviewer package becomes release material.

Optional: benchmark one interchange proposal (for example AIMEM or
memorywire) against the same ablation cells.

Claims to avoid: no "first" statements, no provider ranking, no claim that
products cannot supply the assisted semantics in other configurations.

## IEEE Software

**Status: READY**

Strongest practitioner framing: "benchmarks attribute governance guarantees
to memory products that their adapters and runners actually supply." The
capability matrix (product/adapter/runner/reader/scorer) is directly useful
to architects who evaluate memory vendors, and the deletion and Mem0 native
isolation results give practitioners a positive contrast. Framing should be
an empirical field note with the matrix as the central artifact.

## InfoQ

**Status: READY**

Recommended framing: "when you compare AI memory systems, separate the
product from the harness." The temporal and scope ablation numbers make a
concrete, non-overclaimed practitioner story: which questions a vendor
benchmark can answer, and why layer attribution matters when choosing memory
infrastructure.

## W3C AI Agent Memory Interoperability Community Group

**Status: CONTRIBUTE AFTER PAPER**

Evidence-backed requirements the corrected experiments can contribute:

- interchange and export formats should carry explicit source authority and
  provenance fields, because removal of those fields takes provenance
  correctness from 1.000 to 0.000 in this harness;
- temporal eligibility and validity-window semantics should be first-class,
  because as-of filtering is the single largest benchmark-supplied effect
  measured here;
- principal/scope identity should be representable in stored memory objects,
  because two of three tested products rely on application-side filtering.

No new protocol is proposed. Contribution happens by raising these as test
cases against existing group work after the paper is out.

## IETF

**Status: ENGAGE EXISTING DRAFT AUTHORS**

The experiments do not demonstrate a protocol gap that justifies a new
Internet-Draft. AIMEM Bundle, ApertoMemory, and SAIHM drafts already cover
portable memory objects, provenance, and custody. The measured provenance and
temporal dependencies are empirical requirements that fit existing work.
Engage draft authors with these results; do not write a competing draft.

## Future work (recorded, not started)

- provenance ablation with a larger query set;
- a second corpus or provider replication;
- testing one interchange proposal (AIMEM or memorywire) against the ablation
  cells;
- a reader-model sweep to separate reader capability from benchmark metadata.

None of these are authorized to run without a new instruction.
