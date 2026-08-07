# Contributing to AMSB

Welcome. AMSB values new provider adapters, configuration corrections,
lifecycle tests, recovery tests, capability-attribution properties,
reproducibility improvements, documentation, and bug fixes.

## Scope

AMSB is a provider-neutral evaluation framework. Contributions that add a
provider, improve attribution, or make reproduction easier are in scope.
Contributions that turn AMSB into a leaderboard, a migration framework, or a
new memory product are out of scope.

## Provider benchmark contributions must specify

- exact upstream version and commit
- installation procedure
- controlled/native support (with `tracks` declared)
- embedding configuration
- LLM configuration (or its absence)
- declared capabilities (product/adapter/runner/reader/scorer/partial/
  unsupported)
- benchmark-supplied capabilities (never attributed to the product)
- known unsupported behavior

## Negative provider conclusions

Before publishing a severe negative provider conclusion, confirm the
product interface independently: reproduce the finding with a
provider-independent smoke test and record it. A harness or configuration
mistake is a research finding, not a provider defect.

## Workflow

1. Fork and branch.
2. Follow [docs/adding-a-provider.md](docs/adding-a-provider.md) for provider
   work.
3. Keep the default test suite green:

   ```bash
   uv sync
   uv run pytest
   ```

   Environment-gated tests (`SOVBENCH_RUN_<NAME>=1`) must skip cleanly when
   the provider is absent.
4. Run `uv run python scripts/validate_provider.py --provider <name>` for
   provider changes.
5. Record exact pins, configuration, and capability attribution in the
   provider directory, registry entry, and manifest.
6. Open a pull request describing methodology and evidence.

## Standards

- No secrets, credentials, or private gold in any contribution.
- Frozen research artifacts are not edited; corrections are additive
  (errata style).
- Never fake a capability; unsupported is a valid, recorded outcome.
- Results are bounded: no "best provider" claims from this framework alone.

## Code of conduct

See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
