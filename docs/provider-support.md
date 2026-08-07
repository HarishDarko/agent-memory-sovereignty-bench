# Provider Support

Existing integrations (exact researched pins, preserved unchanged):

| Provider | Version | Controlled | Native | Deletion | Principal | Scope | Export | Recovery |
|---|---|---:|---:|---|---|---|---|---|
| Mem0 OSS | 2.0.17 (`3f39fba...`) | yes | yes | native | native | partial | partial | partial |
| Hindsight | 0.8.6 (`797faf7...`) | yes | yes | native | assisted | assisted | yes | yes |
| GBrain | 0.42.73.2 (`15b9863d...`) | yes | partial | native | assisted | assisted | yes | yes |
| OptMem | 1fb164c | yes | no | unsupported | assisted | assisted | partial | partial |

Coverage notes:

- "assisted" means the benchmark runner supplies the guarantee; the product
  stores the data but does not enforce it natively.
- "partial" means some aspects are native and others are supplied.
- OptMem's pinned upstream has no license file; treat as all-rights-reserved
  and review before use.

This is integration/test coverage. It is not a provider quality ranking, and
results depend on the exact pins and configurations recorded in each
`providers/<name>/config.toml`.

Controls (not memory systems) included in the suite: no-memory, oracle,
random-retrieval, full-context, BM25 pure, BM25 SQLite FTS.
