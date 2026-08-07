# Dataset card — DEV personal corpus (v2)

## Identity

- **Split:** DEV (public, committed)
- **Generator:** `benchmark/datasets/generator_v2.py`
- **Generator version:** v2
- **Seed:** `20260805` (public, deterministic)
- **Generated:** 2026-08-06
- **Contents:** 105 events, 80 queries, 80 ground-truth rows

## Synthetic-only guarantee

Every person, name, brand, value, identifier, and relationship in this corpus
is synthetic and generated after the reader checkpoint release date. Nothing
here is derived from real personal data, private correspondence, or any
provider's training data.

## Taxonomy (17 query kinds)

current_state, historical, supersession, changed_preference,
temporary_validity, expiry, abstention, multi_hop, authority_conflict,
provenance, cross_user, role_group, deletion, do_not_store, poisoning,
recovery, migration.

Per-person storylines cover initial value -> preference change -> correction,
planning with validity windows, and trials with expiry. Corpus-level specials
cover relationships (multi-hop), authority conflicts, provenance, work-scoped
role access, deletion and do-not-store lifecycle actions, poisoning attempts,
recovery and migration labels, cross-user requester isolation, abstention, and
noise.

## Split hygiene

- All events belong to owner `user_001`; `subject` names the entity a fact is
  about. Cross-user and role queries use other requesters.
- Answer values come from the `dev` pool in `DOMAIN_VALUE_SETS`, disjoint from
  the `pack-1..3` pools used by the hidden TEST packs.
- Verified by `scripts/audit_dataset.py` against the hidden packs and the
  commitment in `datasets/commitments/test-v1.json`.

## Usage

- DEV is the only split used for adapter development and configuration tuning.
- It is public; treat every number produced from it as plumbing evidence, not
  benchmark results.
