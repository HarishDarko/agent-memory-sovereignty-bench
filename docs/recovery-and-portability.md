# Recovery and Portability

## Four separate concepts

1. **State ownership:** can the user physically possess the meaningful state?
2. **Same-system recoverability:** can a fresh instance of the same
   implementation recover usable state?
3. **Semantic portability:** does meaning survive outside the original
   implementation?
4. **Behavioral portability:** can another implementation reproduce
   equivalent behavior?

Same-system recovery does not imply semantic or behavioral portability. The
researched Semantic Exit experiment corrected exactly this confusion: an
export that restores the same product can still discard provenance,
authority, temporal history, and explicit-user-versus-model-derived status.

No cross-provider migration was executed in this research. A migration
framework is not part of AMSB.

## What the corrected research found

- Hindsight's whole-bank export/import restores memories; the earlier
  version-only export result was caused by using the wrong export surface
  (recorded in the errata).
- GBrain's canonical Markdown/Git brain is the durable state; PGLite is a
  rebuildable derived index, and the generated export directory is not
  equivalent to the canonical brain without the documented sync/rebuild.
- Mem0 OSS's maximal documented exit state is `get_all()` plus
  `history(memory_id)`; raw source-event identity is not preserved.

Details: `docs/reports/semantic-memory-exit-v1-corrected.md` and
`docs/reports/semantic-memory-exit-v1-errata.md`.

## Export evaluation

For each provider, AMSB records the canonical persisted state, documented
export mechanisms, human readability, raw-event preservation, derived-memory
preservation, timestamps, provenance, authority, supersession, scopes,
deletion/tombstone state, and index rebuildability.
