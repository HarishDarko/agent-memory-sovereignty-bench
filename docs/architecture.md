# AMSB Architecture

## Pipeline

```text
canonical AMSB event
   -> provider adapter (providers/<name>/adapter.py)
   -> provider storage/retrieval
   -> AMSB-controlled eligibility/governance where the protocol requires
   -> common stateless reader
   -> deterministic scorer against private gold
```

## Packages

| Path | Responsibility |
|---|---|
| `benchmark/` | runner, scorer, events, clock, config, manifests, statistics, snapshots, token budget, lifecycle, model gateway, capability attribution and analysis, provider views, dataset generators, isolation probes |
| `contamination/` | preflight isolation suite (egress, cross-provider state, gold access) |
| `providers/` | adapter interface support (`compliance.py`, `registry.py`), baselines, and memory provider adapters with per-provider `config.toml` and `manifest.toml` |
| `schemas/` | JSON schemas for events, queries, ground truth, manifests, provider capabilities, result bundles |
| `datasets/` | public DEV corpus, example corpora, commitment hashes |
| `protocols/` | frozen research protocols (v1, capability-attribution-v1) |
| `prompts/` | versioned reader prompts |
| `scripts/` | runners, analyzers, generators, validation |
| `docker/` | clean-room compose patterns and provider images |
| `tests/` | unit, contract, and integration suites |
| `reports/` | published result artifacts |

## Provider boundary

The central scientific machinery (runner, scorer, metrics, datasets, gold,
statistics, lifecycle, attribution analysis) never imports provider names.
Providers are constructed through `providers/registry.create_provider(name,
data_dir, **kwargs)`, which reads `providers/registry.json`. A provider entry
declares:

- exact upstream pin (`meta.upstream_commit`, `meta.upstream_version`)
- factory reference (`factory`: `module:function`)
- optional environment-mapped factory arguments (`factory_kwargs_env`)
- tracks (`tracks`: `{controlled, native}`)
- optional native-view hook (`native_view`: `module:function`)
- capability manifest path (`manifest`)

Adding a provider touches only `providers/<name>/`, `providers/registry.json`,
`pyproject.toml` (optional deps), and `tests/contract/`.

## Reader and scorer

The reader is stateless: two messages (system prompt + query with evidence),
temperature 0.0, no conversation history, fixed evidence budget. The scorer
is deterministic, typed, and reads private gold that is never mounted into
provider runtimes. Reader and scorer are identical across providers.

The reader is an independent, configuration-selected layer
(`benchmark/model_gateway.py`): the default `offline` mode is a deterministic
stub with no API calls, and the `deepseek` mode is the frozen reference
reader used for the AMSB Protocol v1 model-backed experiments. A future
contributor adds another reader by implementing a `BaseGateway` subclass and
registering it in `get_gateway()`; memory-provider adapters are not involved.
No other reader integrations are shipped. AMSB is not tied to DeepSeek:
DeepSeek V4 Flash is required only for exact reproduction of the historical
V1 model-backed results.

## Fail-closed invariants

- one provider per run; no cross-provider volumes, databases, caches, or
  networks
- deterministic benchmark clock (never wall-clock "today" for scoring)
- state hash equality before and after every retrieval
- gold never readable by providers or readers
- provider containers have no uncontrolled egress (model gateway only)
- unsupported capabilities recorded, never faked
