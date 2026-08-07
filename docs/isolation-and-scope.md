# Isolation and Scope

## Cross-provider isolation

One provider per run. No cross-provider volumes, databases, caches, queues,
or networks. Provider containers have no uncontrolled egress; the only
external route is the model gateway.

## Principal and scope tests

The corpus includes cross-user and role-group cases. For each case:

- `D0-native`: provider's own principal/bank semantics only; no benchmark
  principal/scope post-filter.
- `D1-assisted`: the same raw result plus benchmark principal and scope
  filtering.

Metrics: cross-principal evidence count, wrong-scope evidence count,
unauthorized answer rate on gold-abstain cases, answer correctness, paired
delta, and evidence-set change rate.

## Researched result

| Provider | D0 correctness | D1 correctness | Cross-principal evidence |
|---|---:|---:|---|
| GBrain | 0.333 | 1.000 | 306 to 0 |
| Hindsight | 0.333 | 1.000 | 483 to 0 |
| Mem0 | 1.000 | 1.000 | 0 to 0 |

Mem0's native `user_id` search filter provides principal isolation in the
product. GBrain's global CLI search and Hindsight's single-bank recall do
not; their isolation in this benchmark is runner-supplied. The preregistered
security-count exception applies to the nonzero-to-zero leakage transitions.

Caveat: the assisted scope condition (`D1-assisted`) also applied temporal
eligibility filtering (`available_at <= as_of`), so the correctness deltas
above combine scope and temporal interventions. The cross-principal
evidence exposure (raw counts and their removal) is directly observed;
attributing the full correctness delta to scope filtering alone is not
supported. See `docs/scientific-audit.md`.

## Contamination preflight

`contamination/` implements the preflight suite: egress checks, cross-user
leakage canaries, gold-access checks, and state-hash verification. A run
whose preflight fails is invalid.
