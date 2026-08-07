# datasets/dev

Public synthetic development corpus (deterministic, seeded generator in
`benchmark/corpus.py`; CLI: `scripts/generate_dev_corpus.py`).

Used to build adapters, debug the harness, choose reasonable provider
configurations, and verify scoring. Never used for provider-specific tuning of
the hidden TEST split.

## Layout

- `personal/events.jsonl` - synthetic personal-memory events (person, scope,
  authority, source, kind, timestamps, supersession).
- `personal/queries.jsonl` - questions with principal/scope/as_of and a kind
  label. Never contains answers.
- `personal/ground_truth.jsonl` - public DEV gold (answer, abstain flag, gold
  event ids). The scorer reads this for DEV runs; the hidden TEST gold lives in
  `scorer_private/` and is gitignored.

## Coverage (per canonical plan section 13)

stable facts, explicit/implicit preferences, changes and corrections, temporary
plans with expiry, current vs historical state, abstention (synthetic secrets),
multi-hop relationships, do-not-remember, deletion requests, poison/authority
conflicts, cross-user isolation, and noise.

Regenerate with: `python scripts/generate_dev_corpus.py`
