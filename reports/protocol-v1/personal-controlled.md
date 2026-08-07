# Personal Controlled Benchmark - Protocol v1

Generated 2026-08-06T20:41:55Z; freeze tag protocol-v1-freeze; freeze verified: True.

No winner is declared. Comparisons are labeled resolved / unresolved / unsupported / invalid.

## Metric matrix

| Participant | Attempts | Reader acc. | Abstain acc. | Chain@5 | Gold recall@5 | Pass@1 | All-success | Cost USD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| bm25-pure | 576 | 0.9668 | 0.9746 | 0.9818 | 0.9909 | 0.9635 | 0.9583 | 0.156159 |
| bm25-sqlite-fts | 576 | 0.9668 | 0.9785 | 0.9818 | 0.9909 | 0.9635 | 0.9635 | 0.133345 |
| full-context | 576 | 0.8594 | 0.8594 | 0.0545 | 0.0636 | 0.8594 | 0.8594 | 0.271538 |
| gbrain | 576 | 0.967 | 0.9844 | 0.9697 | 0.9758 | 0.9688 | 0.9635 | 0.206131 |
| hindsight | 576 | 0.9826 | 0.9826 | 0.9455 | 0.9545 | 0.9844 | 0.9792 | 0.390342 |
| mem0 | 576 | 0.974 | 0.9826 | 0.9515 | 0.9606 | 0.974 | 0.9688 | 0.233803 |
| no-memory | 576 | 0.1406 | 0.1406 | 0.0 | 0.0 | 0.1406 | 0.1406 | 0.063606 |
| optmem | 64 | None | None | None | None | 0.0 | 0.0 | 0.050508 |
| oracle | 576 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 0.064997 |
| random-retrieval | 576 | 0.3646 | 0.4688 | 0.1636 | 0.1636 | 0.3646 | 0.3646 | 0.140504 |

## Paired comparisons (resolved only)

| Metric | A | B | Delta | CI low | CI high | Label |
|---|---|---|---:|---:|---:|---|
| chain_complete@5 | no-memory | oracle | -1.0 | -1.0 | -1.0 | resolved |
| chain_complete@5 | no-memory | random-retrieval | -0.163636 | -0.245098 | -0.096045 | resolved |
| chain_complete@5 | no-memory | bm25-pure | -0.981818 | -1.0 | -0.947368 | resolved |
| chain_complete@5 | no-memory | bm25-sqlite-fts | -0.981818 | -1.0 | -0.947368 | resolved |
| chain_complete@5 | no-memory | gbrain | -0.969697 | -1.0 | -0.931034 | resolved |
| chain_complete@5 | no-memory | mem0 | -0.951515 | -0.987179 | -0.915152 | resolved |
| chain_complete@5 | no-memory | hindsight | -0.945455 | -0.983333 | -0.90303 | resolved |
| chain_complete@5 | oracle | random-retrieval | 0.836364 | 0.754902 | 0.903955 | resolved |
| chain_complete@5 | oracle | full-context | 0.945455 | 0.87234 | 1.0 | resolved |
| chain_complete@5 | random-retrieval | bm25-pure | -0.818182 | -0.887006 | -0.740741 | resolved |
| chain_complete@5 | random-retrieval | bm25-sqlite-fts | -0.818182 | -0.887006 | -0.740741 | resolved |
| chain_complete@5 | random-retrieval | gbrain | -0.806061 | -0.87931 | -0.726667 | resolved |
| chain_complete@5 | random-retrieval | mem0 | -0.787879 | -0.84127 | -0.72093 | resolved |
| chain_complete@5 | random-retrieval | hindsight | -0.781818 | -0.866667 | -0.687075 | resolved |
| chain_complete@5 | full-context | bm25-pure | -0.927273 | -0.983051 | -0.857143 | resolved |
| chain_complete@5 | full-context | bm25-sqlite-fts | -0.927273 | -0.983051 | -0.857143 | resolved |
| chain_complete@5 | full-context | gbrain | -0.915152 | -0.967213 | -0.843972 | resolved |
| chain_complete@5 | full-context | mem0 | -0.89697 | -0.963636 | -0.810606 | resolved |
| chain_complete@5 | full-context | hindsight | -0.890909 | -0.939394 | -0.824074 | resolved |
| reader_accuracy | no-memory | oracle | -0.859375 | -0.931034 | -0.786885 | resolved |
| reader_accuracy | no-memory | random-retrieval | -0.223958 | -0.269504 | -0.184211 | resolved |
| reader_accuracy | no-memory | full-context | -0.71875 | -0.774194 | -0.666667 | resolved |
| reader_accuracy | no-memory | bm25-pure | -0.822917 | -0.89899 | -0.743056 | resolved |
| reader_accuracy | no-memory | bm25-sqlite-fts | -0.822917 | -0.89899 | -0.743056 | resolved |
| reader_accuracy | no-memory | gbrain | -0.828125 | -0.924242 | -0.730159 | resolved |
| reader_accuracy | no-memory | mem0 | -0.833333 | -0.910448 | -0.75 | resolved |
| reader_accuracy | no-memory | hindsight | -0.84375 | -0.927536 | -0.754098 | resolved |
| reader_accuracy | oracle | random-retrieval | 0.635417 | 0.553333 | 0.707071 | resolved |
| reader_accuracy | oracle | full-context | 0.140625 | 0.114754 | 0.173913 | resolved |
| reader_accuracy | random-retrieval | full-context | -0.494792 | -0.555556 | -0.427778 | resolved |
| reader_accuracy | random-retrieval | bm25-pure | -0.598958 | -0.681592 | -0.502732 | resolved |
| reader_accuracy | random-retrieval | bm25-sqlite-fts | -0.598958 | -0.681592 | -0.502732 | resolved |
| reader_accuracy | random-retrieval | gbrain | -0.604167 | -0.699454 | -0.497076 | resolved |
| reader_accuracy | random-retrieval | mem0 | -0.609375 | -0.691176 | -0.511111 | resolved |
| reader_accuracy | random-retrieval | hindsight | -0.619792 | -0.705556 | -0.516908 | resolved |
| reader_accuracy | full-context | bm25-pure | -0.104167 | -0.131148 | -0.069182 | resolved |
| reader_accuracy | full-context | bm25-sqlite-fts | -0.104167 | -0.131148 | -0.069182 | resolved |
| reader_accuracy | full-context | gbrain | -0.109375 | -0.163934 | -0.054545 | resolved |
| reader_accuracy | full-context | mem0 | -0.114583 | -0.142157 | -0.076923 | resolved |
| reader_accuracy | full-context | hindsight | -0.125 | -0.169231 | -0.078947 | resolved |
| abstain_accuracy | no-memory | oracle | -0.859375 | -0.931034 | -0.786885 | resolved |
| abstain_accuracy | no-memory | random-retrieval | -0.328125 | -0.367232 | -0.294118 | resolved |
| abstain_accuracy | no-memory | full-context | -0.71875 | -0.774194 | -0.666667 | resolved |
| abstain_accuracy | no-memory | bm25-pure | -0.833333 | -0.910448 | -0.75 | resolved |
| abstain_accuracy | no-memory | bm25-sqlite-fts | -0.833333 | -0.910448 | -0.75 | resolved |
| abstain_accuracy | no-memory | gbrain | -0.84375 | -0.927536 | -0.754098 | resolved |
| abstain_accuracy | no-memory | mem0 | -0.84375 | -0.927536 | -0.754098 | resolved |
| abstain_accuracy | no-memory | hindsight | -0.84375 | -0.927536 | -0.754098 | resolved |
| abstain_accuracy | oracle | random-retrieval | 0.53125 | 0.461111 | 0.599034 | resolved |
| abstain_accuracy | oracle | full-context | 0.140625 | 0.114754 | 0.173913 | resolved |
| abstain_accuracy | random-retrieval | full-context | -0.390625 | -0.447917 | -0.338624 | resolved |
| abstain_accuracy | random-retrieval | bm25-pure | -0.505208 | -0.581699 | -0.424242 | resolved |
| abstain_accuracy | random-retrieval | bm25-sqlite-fts | -0.505208 | -0.581699 | -0.424242 | resolved |
| abstain_accuracy | random-retrieval | gbrain | -0.515625 | -0.595628 | -0.430303 | resolved |
| abstain_accuracy | random-retrieval | mem0 | -0.515625 | -0.595628 | -0.430303 | resolved |
| abstain_accuracy | random-retrieval | hindsight | -0.515625 | -0.595628 | -0.430303 | resolved |
| abstain_accuracy | full-context | bm25-pure | -0.114583 | -0.142157 | -0.076923 | resolved |
| abstain_accuracy | full-context | bm25-sqlite-fts | -0.114583 | -0.142157 | -0.076923 | resolved |
| abstain_accuracy | full-context | gbrain | -0.125 | -0.169231 | -0.078947 | resolved |
| abstain_accuracy | full-context | mem0 | -0.125 | -0.169231 | -0.078947 | resolved |
| abstain_accuracy | full-context | hindsight | -0.125 | -0.169231 | -0.078947 | resolved |
| gold_evidence_recall@5 | no-memory | oracle | -1.0 | -1.0 | -1.0 | resolved |
| gold_evidence_recall@5 | no-memory | random-retrieval | -0.163636 | -0.245098 | -0.096045 | resolved |
| gold_evidence_recall@5 | no-memory | full-context | -0.063636 | -0.134615 | -0.016393 | resolved |
| gold_evidence_recall@5 | no-memory | bm25-pure | -0.990909 | -1.0 | -0.973684 | resolved |
| gold_evidence_recall@5 | no-memory | bm25-sqlite-fts | -0.990909 | -1.0 | -0.973684 | resolved |
| gold_evidence_recall@5 | no-memory | gbrain | -0.975758 | -1.0 | -0.938596 | resolved |
| gold_evidence_recall@5 | no-memory | mem0 | -0.960606 | -0.988701 | -0.930818 | resolved |
| gold_evidence_recall@5 | no-memory | hindsight | -0.954545 | -0.983333 | -0.92623 | resolved |
| gold_evidence_recall@5 | oracle | random-retrieval | 0.836364 | 0.754902 | 0.903955 | resolved |
| gold_evidence_recall@5 | oracle | full-context | 0.936364 | 0.865385 | 0.983607 | resolved |
| gold_evidence_recall@5 | random-retrieval | bm25-pure | -0.827273 | -0.893939 | -0.75 | resolved |
| gold_evidence_recall@5 | random-retrieval | bm25-sqlite-fts | -0.827273 | -0.893939 | -0.75 | resolved |
| gold_evidence_recall@5 | random-retrieval | gbrain | -0.812121 | -0.885246 | -0.729167 | resolved |
| gold_evidence_recall@5 | random-retrieval | mem0 | -0.79697 | -0.849462 | -0.726496 | resolved |
| gold_evidence_recall@5 | random-retrieval | hindsight | -0.790909 | -0.873333 | -0.694444 | resolved |
| gold_evidence_recall@5 | full-context | bm25-pure | -0.927273 | -0.983051 | -0.857143 | resolved |
| gold_evidence_recall@5 | full-context | bm25-sqlite-fts | -0.927273 | -0.983051 | -0.857143 | resolved |
| gold_evidence_recall@5 | full-context | gbrain | -0.912121 | -0.966667 | -0.840909 | resolved |
| gold_evidence_recall@5 | full-context | mem0 | -0.89697 | -0.963636 | -0.810606 | resolved |
| gold_evidence_recall@5 | full-context | hindsight | -0.890909 | -0.939394 | -0.824074 | resolved |
| evidence_id_precision | no-memory | oracle | -0.859375 | -0.931034 | -0.786885 | resolved |
| evidence_id_precision | no-memory | random-retrieval | -0.224826 | -0.273069 | -0.181965 | resolved |
| evidence_id_precision | no-memory | full-context | -0.701388 | -0.75084 | -0.65525 | resolved |
| evidence_id_precision | no-memory | bm25-pure | -0.827544 | -0.893281 | -0.761572 | resolved |
| evidence_id_precision | no-memory | bm25-sqlite-fts | -0.846064 | -0.912036 | -0.779902 | resolved |
| evidence_id_precision | no-memory | gbrain | -0.810762 | -0.891491 | -0.729683 | resolved |
| evidence_id_precision | no-memory | mem0 | -0.817477 | -0.883332 | -0.750736 | resolved |
| evidence_id_precision | no-memory | hindsight | -0.833043 | -0.901822 | -0.764658 | resolved |
| evidence_id_precision | oracle | random-retrieval | 0.634549 | 0.553498 | 0.704546 | resolved |
| evidence_id_precision | oracle | full-context | 0.157988 | 0.124379 | 0.195263 | resolved |
| evidence_id_precision | random-retrieval | full-context | -0.476561 | -0.539561 | -0.409188 | resolved |
| evidence_id_precision | random-retrieval | bm25-pure | -0.602718 | -0.673644 | -0.525044 | resolved |
| evidence_id_precision | random-retrieval | bm25-sqlite-fts | -0.621238 | -0.689888 | -0.544444 | resolved |
| evidence_id_precision | random-retrieval | gbrain | -0.585936 | -0.665848 | -0.500308 | resolved |
| evidence_id_precision | random-retrieval | mem0 | -0.592651 | -0.66263 | -0.516725 | resolved |
| evidence_id_precision | random-retrieval | hindsight | -0.608217 | -0.680042 | -0.528536 | resolved |
| evidence_id_precision | full-context | bm25-pure | -0.126157 | -0.151041 | -0.098705 | resolved |
| evidence_id_precision | full-context | bm25-sqlite-fts | -0.144677 | -0.169888 | -0.119004 | resolved |
| evidence_id_precision | full-context | gbrain | -0.109374 | -0.151143 | -0.060114 | resolved |
| evidence_id_precision | full-context | mem0 | -0.116089 | -0.141906 | -0.088939 | resolved |
| evidence_id_precision | full-context | hindsight | -0.131655 | -0.162109 | -0.105581 | resolved |

## Not-run participants

- none
