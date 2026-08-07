# GBrain Configuration Summary (Capability Attribution Ablation v1)

For maintainer review before publication. Do not send without instruction.

## Pinned version

- Upstream commit: `15b9863d13635d173562a54f55a1d388bfcf546b`
- Version label: 0.42.73.2
- Local binary: `%USERPROFILE%\.bun\install\global\node_modules\gbrain\src\cli.ts` (Bun runtime)

## Configuration used

- Storage: PGLite under the GBrain home (`brain.pglite`), one home per pack run
- Embeddings: `--no-embedding` (keyword search only, per the frozen V1 control)
- Retrieval: pinned CLI `search` command; stopword and output parsing in
  `benchmark/capability_provider_views.py`
- Ingestion: adapter writes one Markdown page per event with frontmatter
  (principal, subject, scope, authority, source, available_at, valid_from,
  valid_to, kind) into the brain directory
- Deletion: adapter maps abstract delete events to the pinned CLI delete
  operation

## Native vs controlled difference

- Controlled/native view: product CLI search without benchmark post-filtering
- Assisted view: same raw result filtered by benchmark eligibility
  (`available_at <= as_of`, principal equality, scope equality)

## Embedding model

None. `--no-embedding` configuration; semantic retrieval not exercised in
this experiment.

## LLM model

None inside the provider. The common reader (`deepseek-v4-flash`) runs outside
GBrain through the benchmark gateway.

## Retrieval configuration

Search terms: first six lowercase alphanumeric terms (length >= 2) after
stopword removal; queries "terms joined" then individual terms; up to 20
matches.

## Export/recovery method

Not exercised in this experiment (deletion and retrieval only).

## Deviations from documented defaults

- Embeddings disabled (`--no-embedding`)
- Adapter-written frontmatter supplies governance metadata
- Single global brain per run; no multi-user native scoping (global CLI
  search)

## Exact factual claims involving this provider

- Temporal correctness: 0.537 native to 1.000 assisted (material, Holm p
  3.1e-05)
- Scope: 306 cross-principal evidence items and 18 unauthorized answers
  natively, both zero after benchmark post-filtering (qualitative material
  transition)
- Deletion: zero deleted evidence retrievable after native delete
- Authority: 0.667 to 1.000 assisted; directional only
- Provenance: 0.000 to 0.889 with metadata; directional only
