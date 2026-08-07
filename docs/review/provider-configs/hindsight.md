# Hindsight Configuration Summary (Capability Attribution Ablation v1)

For maintainer review before publication. Do not send without instruction.

## Pinned version

- Upstream commit: `797faf7981ce9332e2ce7c922471b72b506b4065`
- Version label: 0.8.6
- Image: `sovbench-hindsight:797faf7-cached` (local model cache baked in;
  digest `sha256:2ad9f581...` recorded in the compose file)

## Configuration used

- `HINDSIGHT_API_LLM_PROVIDER=none`: no provider-side LLM features
- Database: pgvector PostgreSQL, one isolated bank per pack run
- Embeddings/reranker: local `BAAI/bge-small-en-v1.5` and
  `cross-encoder/ms-marco-MiniLM-L-6-v2`; `HF_HUB_OFFLINE=1`,
  `TRANSFORMERS_OFFLINE=1`
- Network: provider API and DB on an internal-only Docker network; the
  benchmark-owned sidecar forwards host traffic

## Native vs controlled difference

- Native view: pinned recall endpoint with `query_timestamp` supplied by the
  application (required by the product API) and no benchmark post-filtering
- Assisted view: same raw result filtered by benchmark principal/scope
  equality
- Temporal ablation: descriptive only; a parameter-free native condition is
  not a meaningful configuration for this pinned API

## Embedding model

Local `BAAI/bge-small-en-v1.5` (baked into the cached image, offline).

## LLM model

None inside the provider. Common reader `deepseek-v4-flash` runs outside
through the benchmark gateway.

## Retrieval configuration

Recall payload: `{"query": ..., "budget": "high", "max_tokens": 4096,
"query_timestamp": query.as_of}`.

## Export/recovery method

Not exercised in this experiment (whole-bank export/import was covered in the
corrected Semantic Exit phase).

## Deviations from documented defaults

- LLM provider disabled (documented option)
- Offline model cache
- Single bank per run; principal/scope is benchmark metadata, not a native
  product dimension

## Exact factual claims involving this provider

- Scope: 483 cross-principal evidence items and 18 unauthorized answers
  natively, both zero after benchmark post-filtering (qualitative material
  transition)
- Deletion: zero deleted evidence retrievable after native delete
- Authority: 0.889 to 1.000 assisted; directional only
- Provenance: 0.000 to 1.000 with metadata; directional only
- Temporal: descriptive only (application-supplied `query_timestamp`)
