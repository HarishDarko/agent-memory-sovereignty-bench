# Controlled vs Native Evaluation

## Controlled track

```text
canonical AMSB event
   -> provider adapter
   -> provider storage/retrieval
   -> AMSB-controlled eligibility/governance where the protocol requires
   -> common reader
   -> common scorer
```

Question: given normalized memory objects and benchmark-controlled semantics,
how does the underlying system store and retrieve evidence?

The controlled track deliberately disables provider-native extraction so the
comparison isolates storage/retrieval behavior. Configurations are frozen
per provider (see `providers/<name>/config.toml`).

## Native track

```text
raw event
   -> provider-native memory pipeline
   -> extraction / consolidation / reflection / summarization / graph
      construction / native retrieval policies
   -> common reader/scorer where applicable
```

Question: what does the actual memory product do with the same events?

Native behavior may differ substantially and is preserved rather than
normalized away. The native track is optional: a provider may declare
`tracks.native = false` and document why.

## Why they stay separate

The researched evidence shows why merging is misleading. In capability
attribution v1, native Mem0 authority recall differed from controlled
behavior, and temporal correctness depended on runner-side filtering in the
controlled configuration. Reporting one blended score would attribute
benchmark assistance to the product.

## Capability ownership

For every property, record who implements it: product, adapter, runner,
reader, or scorer. See `docs/capability-attribution.md`.
