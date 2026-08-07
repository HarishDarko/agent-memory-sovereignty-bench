# AMSB Release Readiness

**Date:** 2026-08-07

## Project

Agent Memory Sovereignty Bench (AMSB), v1.0.0. Provider-neutral evaluation
framework for persistent agent memory.

## Extraction status

- Curated from `memory-sovereignty-bench` (source HEAD `bee627b`), fresh Git
  history, no `.git` copied.
- 228 files copied; machine paths sanitized; private artifacts excluded
  (`runs/`, `scorer_private/`, `.optmem`, caches); four untracked synthesis
  drafts and one-off forensic scripts excluded (documented in
  `OSS-EXTRACTION-PLAN.md`).
- Packaging regenerated (`pyproject.toml`, `uv.lock`); the freeze test
  records the one intentional content divergence (lock group).

## Security audit

- Secret scan: no credentials found. The only pattern hits are a placeholder
  (`"<key>"` in the reader-pilot protocol doc) and a test assertion.
- Personal-path scan: clean after sanitization (user paths converted to
  `%USERPROFILE%` / `Path.home()` forms).
- `.env.example` provided; real keys are environment-only and never
  committed; `.gitignore` excludes `.env` and `*.env`.
- Private gold (`scorer_private/`) is untracked and gitignored; no gold in
  provider roots, datasets, or reports.
- Docker compose files use a local-only test password (`sovbench/sovbench`),
  documented as non-production.

## Scientific audit

`docs/scientific-audit.md` documents, without altering results:

- the assisted scope condition also applied temporal eligibility filtering;
- the raw/assisted evidence-count differences are eligibility filtering, not
  serialization or budgeting;
- the reconciled cost ledger (`reports/COST-LEDGER.md`).

## Dataset policy

`docs/dataset-policy.md`: DEV corpus and example corpora public; hidden TEST
gold and packs private; commitment hashes published; generators documented.

## Provider integrations

Preserved exact researched pins: Mem0 OSS 2.0.17, Hindsight 0.8.6, GBrain
0.42.73.2, OptMem 1fb164c. No upgrades, no new providers.

## Extensibility assessment

> Can a new Level-1 provider be added without modifying
> runner/scorer/metrics?

**YES.** A Level-1 provider touches only:

- `providers/<name>/adapter.py`
- `providers/<name>/manifest.toml`
- `providers/<name>/config.toml`
- `providers/registry.json` (one entry with a factory reference)
- `tests/contract/test_<name>_adapter.py`
- optionally `pyproject.toml` (dependency extra)

The central runner, scorer, metrics, datasets, gold, statistics, lifecycle
engine, and attribution analysis are untouched. Verified by the template
dry-run and by `scripts/validate_provider.py` (baseline and Mem0).

> Can native providers be added without central benchmark changes?

**YES.** A Level-3 provider implements `native_retrieve` in its adapter and
references it in the registry entry (`native_view`); the central views module
dispatches through the registry hook.

## New-provider dry run

Hypothetical `ExampleProvider` file changes:

1. `providers/example/adapter.py` (new)
2. `providers/example/manifest.toml` (new)
3. `providers/example/config.toml` (new)
4. `providers/example/README.md` (new)
5. `providers/registry.json` (one entry)
6. `tests/contract/test_example_adapter.py` (new)
7. `pyproject.toml` (optional dependency extra, only if pip deps)

No changes to `benchmark/`, `contamination/`, `datasets/`, `schemas/`,
`prompts/`, or the analysis scripts.

## Controlled-track readiness

Ready. Baselines and Mem0 validate through `scripts/validate_provider.py`;
DEV runs use the public corpus and offline reader; the Phase 0 smoke passes
end-to-end with preflight PASS on all six controls.

## Native-track readiness

Ready as documented. Native declarations exist for Mem0 and Hindsight;
GBrain native is partial (controlled keyword configuration); OptMem native
is not implemented. Native behavior is reported separately from controlled
behavior.

## Tests

- Full suite: 303 tests, 0 failures, 39 skips (env-gated provider
  integrations and private-artifact-dependent checks, documented in each
  skip message).
- Smoke: baseline validation PASS, Mem0 validation PASS (local, no paid
  calls), Phase 0 controls PASS, template dry-run PASS.

## License

Apache-2.0 (`LICENSE`); third-party notices in `THIRD_PARTY_NOTICES.md`;
OptMem pin has no upstream license file and is flagged.

## Known technical debt

Recorded in `docs/known-technical-debt.md`; none blocks release.

## Human-review items

1. GitHub repository URL placeholder in `CITATION.cff` and the README clone
   command; fill in when the repository is created.
2. Provider license identifiers recorded from metadata; verify each project's
   license at the pinned commit before any distribution beyond source form.
3. OptMem inclusion decision (pinned upstream has no license file).
4. The `report_*` research scripts reference source-repo commits in
   documentation; the errata trail documents them, and the integrity checks
   are recorded-hash based in AMSB.
5. Decide whether to publish hidden-TEST gold at a later date (currently
   excluded; commitments published).
6. Reviewer pass over `docs/review/` material before any public claims.

## Final recommendation

**READY FOR HUMAN REVIEW.**
