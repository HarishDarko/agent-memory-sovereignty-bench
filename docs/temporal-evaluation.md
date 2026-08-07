# Temporal Evaluation

## As-of queries

Every query carries an `as_of` timestamp from the deterministic benchmark
clock. Evidence is only eligible when `available_at <= as_of`. Current-state,
historical-state, supersession, changed-preference, temporary-validity, and
expiry question families exercise this.

## Paired conditions

- `C0-native`: provider-native/raw retrieval mapped to opaque evidence IDs,
  with no benchmark as-of, current/history, principal, or scope post-filter
  beyond parameters the product API fundamentally requires.
- `C1-assisted`: the same raw result filtered by benchmark eligibility
  (`available_at <= as_of`, principal equality, scope equality).

The same raw retrieval call feeds both conditions, so the only difference is
the benchmark filter.

## Researched result

In capability attribution v1 the temporal effect was the strongest measured
benchmark contribution:

| Provider | C0-native | C1-assisted | Future leaks removed |
|---|---:|---:|---|
| GBrain | 0.537 | 1.000 | 45 to 0 |
| Mem0 | 0.528 | 1.000 | 49 to 0 |

Material by every preregistered gate (Holm p 3.1e-05 / 3.0e-05, bootstrap
intervals excluding zero, 16/17 discordant pairs). Current/historical-state
resolution and future-information blocking were runner functions in this
harness, not product capabilities of the tested configurations.

## Hindsight note

Hindsight's pinned recall API requires an application-supplied
`query_timestamp`, so a parameter-free native condition is not a meaningful
configuration. Its temporal ownership is recorded as
`descriptive-application-timestamp-required`.

## Future-information leakage

Future leakage is measured two ways: the count of future-dated evidence items
in the evidence set, and whether the reader cites future evidence in its
answer. Both are reported per condition.
