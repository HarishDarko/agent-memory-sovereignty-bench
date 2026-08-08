# AMSB Agent Instructions

Working instructions for coding agents (Codex, Claude Code, Cursor, OpenCode,
or similar). This file is public and contains no personal plans.

## Project purpose

AMSB evaluates persistent agent-memory systems. Keep three concepts
distinct:

- **Controlled evaluation**: normalized memory objects through the adapter;
  the benchmark supplies eligibility semantics where the protocol requires.
- **Product-native evaluation**: the provider's real memory pipeline with
  native retrieval; optional per provider.
- **Capability attribution**: each observed capability is attributed to
  Product, Adapter, Runner, Reader, or Scorer.

## Scientific invariant

Do not modify frozen results to make tests or documentation cleaner.

Do not reinterpret benchmark-assisted behavior as product-native behavior.

Core rule:

> Do not call a benchmark-enforced property a memory-product capability.

Reader neutrality:

- DeepSeek is not mandatory for general development; the offline reader is
  the default and needs no key.
- Do not replace the frozen reader (prompt, model, settings) in historical
  protocols; changing it invalidates exact reproduction.
- New reader implementations live in the reader layer
  (`benchmark/model_gateway.py`), separate from memory-provider adapters.
- Changing reader or model changes the experimental configuration; never
  compare results from different readers as though everything else were
  identical.

## Repository architecture

- `providers/` - adapters, capability manifests, `registry.json`
- `benchmark/` - runner, scorer, gateway, statistics, capability attribution
- `contamination/` - preflight isolation suite
- `datasets/` - public DEV corpus, example corpora, commitment hashes
- `protocols/` - frozen research protocols and preregistrations
- `prompts/` - versioned reader prompts
- `schemas/` - JSON schemas
- `scripts/` - runners, analyzers, generators, validation
- `docker/` - clean-room compose patterns and provider images
- `tests/` - unit, contract, integration suites
- `reports/` - published result artifacts
- `docs/` - user and research documentation

## Adding a provider

A Level-1 provider should normally modify only:

- `providers/<name>/adapter.py`
- `providers/<name>/manifest.toml`
- `providers/<name>/config.toml`
- `providers/<name>/README.md`
- one `providers/registry.json` entry
- `tests/contract/test_<name>_adapter.py`
- optionally a `pyproject.toml` dependency extra

It should NOT modify: scorer, metrics, datasets, gold, central scientific
protocol, or frozen reports, unless the user explicitly requires it.

## Controlled vs native

Controlled: canonical events in, normalized semantics, common reader/scorer.
Native: raw events through the provider's own pipeline; behavior is
preserved, not normalized. Native support is optional and must be declared
in the manifest (`tracks.native`). GBrain native TEST was not run; do not
imply otherwise.

## Capability manifest

`providers/<name>/manifest.toml` attributes each capability to
Product/Adapter/Runner/Reader/Scorer with statuses supported, unsupported,
partial, or not evaluated. Follow the researched attribution in
`docs/reports/capability-attribution-v1.md`.

## Unsupported features

Do not emulate an unsupported product capability and attribute it to the
product. Raise `CapabilityNotSupported` and record the status honestly.

## Frozen research

Treat these as frozen: `protocols/`, `datasets/commitments/`,
`reports/protocol-v1/`, `reports/capability-attribution-v1/`, the Semantic
Exit original/errata/corrected reports, and the capability-attribution v1
report. Corrections are additive (errata style), never silent rewrites.

## Required validation before completing code changes

```bash
uv sync
uv run python -B -m unittest discover -s tests
uv run python scripts/validate_provider.py --provider <provider>
```

Relevant smoke tests: `scripts/run_phase0.py`,
`scripts/run_provider_dev.py --provider bm25-pure`. Environment-gated tests
skip when optional provider infrastructure is absent; zero failures is the
bar.

## Privacy

Never add: credentials, hidden TEST gold, private scorer artifacts,
machine-specific paths, personal publication plans, or career/outreach
plans.

## Scope discipline

Do not add providers, datasets, experiments, or methodological changes
unless the user explicitly asks. Do not create GitHub repositories or push
remotes.
