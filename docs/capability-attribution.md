# Capability Attribution

AMSB's signature model distinguishes five layers: **Product, Adapter,
Runner, Reader, Scorer**.

Core rule: **do not call a benchmark-enforced property a memory-product
capability.**

## The capability attribution matrix

Rows are capabilities (factual retrieval, authority representation/reasoning,
provenance representation/reasoning, temporal filtering, current-state
resolution, principal isolation, scope filtering, deletion operation and
verification, read-only guarantee, future filtering, correctness judgment).
Columns are the five layers. Cells use the fixed vocabulary:

- PRIMARY
- CONTRIBUTES
- VERIFIES
- NOT INVOLVED
- NOT OBSERVABLE
- UNSUPPORTED

The complete matrix for the researched providers is in
`docs/reports/capability-attribution-v1.md` (section 15).

## What the experiment found

Using 918 paired reader attempts across GBrain, Mem0, and Hindsight:

- Temporal correctness was essentially runner-supplied: with native
  retrieval GBrain scored 0.537 and Mem0 0.528 on temporal questions with 45
  and 49 future-information leaks; after benchmark as-of filtering both
  scored 1.000 with zero leakage (material by every preregistered gate).
- Principal isolation was runner-supplied for GBrain and Hindsight (306 and
  483 cross-principal items, 18 unauthorized answers each, all reduced to
  zero) and product-native for Mem0 (native `user_id` filter).
- Provenance source identification was 0.000 with text-only evidence and
  0.889-1.000 with benchmark-supplied metadata for all three providers
  (declared underpowered, three queries per provider).
- Authority assistance moved correctness directionally (0.667-0.889 to
  1.000) with metadata and instructions contributing equally.
- Deletion was product-native for all three providers: zero deleted evidence
  remained retrievable after native delete, with no benchmark post-filtering.

## Reporting rule

Result summaries and provider manifests must attribute every observed
capability. A governance result that only exists because the runner filtered
or the adapter supplied metadata is reported as such.
