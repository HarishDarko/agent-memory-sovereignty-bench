# Semantic Memory Exit v1 Dataset Card

This is a small, deterministic, synthetic corpus for the post-freeze semantic
memory exit experiment. It is not a replacement for the frozen protocol-v1
dataset and must not be merged into its scores.

The 24 public source events deliberately combine facts, preferences, changes,
corrections, temporal validity, authority, provenance, principal/scope
boundaries, deletion, explicit user statements, model-derived claims, and an
ambiguous claim. `available_at` is the benchmark ingestion/availability time;
`valid_from` and `valid_to` carry source/event validity where applicable.

The public queries contain no answers or gold evidence IDs. Semantic gold is
kept under `scorer_private/semantic-exit-v1/gold.json` and is never placed in
a provider working directory, container mount, or reader request.

The experiment uses the same synthetic events for GBrain, Mem0 OSS, and
Hindsight, but retains each product's native representation and export
contract. Adapter-added bookkeeping is reported separately from a documented
user export.
