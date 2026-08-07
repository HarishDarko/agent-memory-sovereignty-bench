# Mem0 OSS Configuration Summary (Capability Attribution Ablation v1)

For maintainer review before publication. Do not send without instruction.

## Pinned version

- Upstream commit: `3f39fba28f7781aaf581f64a4af39d017af65835`
- Version label: 2.0.17 (OSS, not hosted platform)

## Configuration used

- `infer=False`: no native LLM extraction; memories are stored from adapter
  text with metadata
- Vector store: local Chroma (no keyword/hybrid support; BM25 scoring
  disabled by the library)
- Embeddings: FastEmbed `BAAI/bge-small-en-v1.5` (local)
- Telemetry: disabled
- Scope: one clean Mem0 state directory per pack run

## Native vs controlled difference

- Native view: `memory.search(query, filters={"user_id": query.principal},
  limit=20)`; `user_id` filter is required by the product interface, so it
  stays in the native condition
- Assisted view: same raw result filtered by benchmark `available_at <= as_of`
  and scope equality

## Embedding model

FastEmbed `BAAI/bge-small-en-v1.5` (local, no network).

## LLM model

None inside the provider (`infer=False`). Common reader `deepseek-v4-flash`
runs outside through the benchmark gateway.

## Retrieval configuration

Semantic similarity only (Chroma lacks keyword search); `limit=20`; native
`user_id` filter retained in both conditions.

## Export/recovery method

Not exercised in this experiment.

## Deviations from documented defaults

- `infer=False` (documented option; disables LLM extraction)
- Telemetry disabled
- Metadata dict carries adapter-written governance fields

## Exact factual claims involving this provider

- Temporal correctness: 0.528 native to 1.000 assisted (material, Holm p
  3.0e-05); future leakage 49 to 0
- Principal isolation: native `user_id` filter already isolates principals
  (cross-principal evidence 0 in both conditions); scope assistance changes
  no correctness (1.000 to 1.000)
- Deletion: zero deleted evidence retrievable after native delete
- Authority: 0.833 to 1.000 assisted; directional only
- Provenance: 0.000 to 1.000 with metadata; directional only
