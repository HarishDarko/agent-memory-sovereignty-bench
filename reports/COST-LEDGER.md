# AMSB Cost Ledger

All values come from recorded manifests and hash-chain ledgers. No missing
values are invented.

## Capability Attribution v1 (hidden TEST, nine packs)

| Provider | Requests | Input tokens | Output tokens | Cost USD | Source |
|---|---:|---:|---:|---:|---|
| GBrain (incl. 2 abandoned calls) | 385 | 609,000 | 331,715 | 0.178140 | `reports/capability-attribution-v1/provider-summaries/gbrain-summary.json` |
| Mem0 | 381 | 676,703 | 298,234 | 0.178244 | `reports/capability-attribution-v1/provider-summaries/mem0-summary.json` |
| Hindsight | 162 | 328,656 | 85,810 | 0.070039 | `reports/capability-attribution-v1/provider-summaries/hindsight-summary.json` |
| **Total** | **928** | **1,614,359** | **715,759** | **0.426423** | |

Pricing: 0.14 USD/M input, 0.28 USD/M output (recorded policy). Model
identity returned on every call: `deepseek-v4-flash`. The USD 0.000715
abandoned-call component is documented in
`protocols/capability-attribution-v1/deviations.md`.

## Reader pilot (2026-08-06)

Usage records in `experiments/reader-pilot/ledger.jsonl`: dry-run $0; live
run usage tokens recorded there with returned model `deepseek-v4-flash`.
Cost at the same policy prices is computable from the ledger; it is reported
in the pilot results JSONs.

## Frozen V1 (Task 15)

Per-provider costs are recorded in `reports/protocol-v1/personal-controlled.*`
and `personal-native.*` (Cost USD column).

## Rules

- The ledger stores hashes, identity, and usage only; never request or
  response content.
- API cost is accounting, never a provider-performance criterion.
