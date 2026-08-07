# Known Technical Debt

Recorded rather than fixed, per the release principle: if debt does not
prevent provider extensibility, installation, security, correctness,
reproducibility, or basic usability, it stays.

- The capability-attribution runner (`scripts/run_capability_attribution.py`)
  still contains some research-era constants (preregistration short commit,
  pricing floats) that could be read from configuration.
- `benchmark/capability_provider_views.py` keeps the three researched
  native views as built-ins; new providers use the registry hook, but the
  built-ins could eventually move into their adapter modules.
- The provider registry mixes two record kinds: contract-verified baseline
  entries and static memory-provider declarations (`contract_status =
  "research-v1"`). A future pass could re-run the compliance contract for
  memory providers and upgrade the status.
- `scripts/run_protocol_v1.py` and follow-up scripts carry research-era
  bookkeeping (environment flags such as `SOVBENCH_PROTOCOL_COST_APPROVED`)
  that is unnecessary for framework use.
- Docker compose files use a local-only test password (`sovbench/sovbench`);
  acceptable for local clean-room runs, not production.
- Ruff is not pinned in the environment; the suite relies on stdlib unittest
  and Git whitespace checks.
- The reader-pilot experiment directory contains live API usage records
  (no response content) that could be moved under `reports/` in a future
  cleanup.
