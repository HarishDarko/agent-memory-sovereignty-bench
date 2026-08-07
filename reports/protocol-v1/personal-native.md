# Personal Controlled Benchmark - Protocol v1

Generated 2026-08-07T02:01:16Z; freeze tag protocol-v1-freeze; freeze verified: True.

No winner is declared. Comparisons are labeled resolved / unresolved / unsupported / invalid.

## Metric matrix

| Participant | Attempts | Reader acc. | Abstain acc. | Chain@5 | Gold recall@5 | Pass@1 | All-success | Cost USD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| hindsight | 576 | 0.9844 | 0.9844 | 0.9576 | 0.9667 | 0.9844 | 0.9844 | 0.877309 |
| mem0 | 576 | 0.941 | 0.941 | 0.9354 | 0.9394 | 0.9062 | 0.9062 | 1.149295 |
| optmem | 0 | None | None | None | None | 0.0 | 0.0 | 0.104674 |

## Paired comparisons (resolved only)

| Metric | A | B | Delta | CI low | CI high | Label |
|---|---|---|---:|---:|---:|---|
| chain_complete@5 | mem0 | hindsight | -0.054545 | -0.108974 | -0.005376 | resolved |
| reader_accuracy | mem0 | hindsight | -0.078125 | -0.128571 | -0.031746 | resolved |
| abstain_accuracy | mem0 | hindsight | -0.078125 | -0.128571 | -0.031746 | resolved |

## Not-run participants

- gbrain: gbrain product-native config requires an embedding provider (ZeroEntropy/OpenAI/Voyage) with credentials not available in this environment
