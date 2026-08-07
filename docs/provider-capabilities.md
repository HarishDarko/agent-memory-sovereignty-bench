# Provider Capabilities

## Capability outcomes

Every provider capability is reported as one of:

- `product` - implemented by the memory product itself
- `adapter` - supplied by the AMSB adapter (metadata, event mapping,
  lifecycle translation)
- `runner` - supplied by the benchmark runner (eligibility filtering, state
  checks)
- `reader` - supplied by the common reader (reasoning from evidence)
- `scorer` - verified by the deterministic scorer
- `partial` - some aspects native, others supplied
- `unsupported` - not implemented; never faked
- `not_applicable` - not meaningful for this provider architecture

## Manifest schema

Each provider declares `providers/<name>/manifest.toml`:

```toml
provider = "example"
version = "0.1.0"
upstream_commit = "..."

[tracks]
controlled = true
native = false

[capabilities.retrieval]
product = true

[capabilities.temporal_filtering]
product = false
runner = true

[capabilities.principal_isolation]
product = false
runner = true

[capabilities.deletion]
product = true
```

Attribution follows the evidence in `docs/capability-attribution.md`. A
benchmark-enforced property is never labeled a product capability.

## Integration levels

- Level 1: controlled retrieval (reset, ingest, retrieve)
- Level 2: lifecycle/governance subset (deletion, isolation, scope, history,
  export, recovery)
- Level 3: product-native pipeline (extraction, consolidation, native
  retrieval, optional native-view hook)

Level 1 is a complete, acceptable contribution.

## Unsupported handling

Unsupported capabilities do not block participation. The adapter raises
`CapabilityNotSupported`; the registry and validation record it as
unsupported; the workload reports `invalid_invariant` only where the protocol
requires the capability. Do not implement missing product behavior in the
adapter and attribute it to the product.
