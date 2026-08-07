# Research History

AMSB preserves the research trail instead of rewriting it. Original
conclusions, retracted conclusions, root causes, and corrected findings are
all kept.

## Timeline

1. **Task 15 benchmark (frozen V1)** - commit `c3007f4` in the source
   repository. Controlled and native results across no-memory, oracle,
   random, BM25/FTS, full-context, OptMem, GBrain, Mem0, and Hindsight.
   Report: `docs/reports/task15-native-track-research-review.md`.
2. **Semantic Exit experiment (original)** -
   `docs/reports/semantic-memory-exit-v1.md`. Initial export/recovery
   findings, some later retracted.
3. **Forensic correction pass** - `docs/reports/semantic-memory-exit-v1-errata.md`
   and `docs/reports/semantic-memory-exit-v1-corrected.md`.
4. **Capability Attribution v1** - `docs/reports/capability-attribution-v1.md`
   with preregistration and deviations in `protocols/capability-attribution-v1/`.
5. **Publication Readiness Review** - `docs/reports/publication-readiness-review.md`
   and `docs/reports/final-publication-decision.md`.

## Retracted or corrected conclusions

| Original claim | Corrected finding | Root cause |
|---|---|---|
| Hindsight's documented exit artifact is nearly empty (`{"version":"1"}`) | Whole-bank export/import restores memories | The original experiment used the wrong export surface (bank config endpoint instead of the whole-bank mechanism) |
| GBrain fresh import restores nothing (all searches empty) | Canonical Markdown/Git brain is the durable state; PGLite is rebuildable, and the generated export directory needs the documented sync/rebuild to function | The experiment treated the generated export directory as equivalent to the canonical brain |
| Mem0 export loses provenance/temporal history | Maximal documented OSS exit state is `get_all()` plus `history(memory_id)`; raw source-event identity is still not preserved | The original used only `get_all()` |

The corrected conclusions are in `semantic-memory-exit-v1-corrected.md`; the
errata records the discrepancy analysis.

## Capability Attribution v1 findings (final)

- Temporal correctness was materially runner-supplied (GBrain 0.537 to 1.000,
  Mem0 0.528 to 1.000 after benchmark as-of filtering; future leakage to
  zero).
- Principal isolation was runner-supplied for GBrain/Hindsight and
  product-native for Mem0.
- Provenance source identification depended entirely on benchmark metadata
  (0.000 to 0.889-1.000; directional, underpowered).
- Deletion was product-native for all three providers.

No provider is declared a winner. Results are bounded to the tested pins,
corpus, prompts, and reader.

## Source provenance

AMSB is a curated open-source distribution of the research repository
`memory-sovereignty-bench` (source HEAD `bee627b`). Scientific commit
references above are preserved verbatim from that history.
