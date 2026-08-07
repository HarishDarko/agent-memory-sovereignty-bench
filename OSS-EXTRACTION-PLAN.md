# AMSB Extraction and Architecture Audit

**Date:** 2026-08-07
**Source repository (read-only):** `C:\Users\<user>\Documents\Codex\memory-sovereignty-bench`
**Source HEAD:** `bee627be0165e4b5ef5ea91ffd0c74bc52a75bf7` (239 tracked files)
**Target repository:** `C:\Users\<user>\Documents\Codex\agent-memory-sovereignty-bench`

This file classifies every major source component and answers the provider
extensibility question before any refactoring. The source repository is
treated as read-only; all OSS work happens in the target.

## 1. Classification

### PUBLIC CORE (working implementation required to run AMSB)

| Path | Contents | Notes |
|---|---|---|
| `benchmark/` | runner, scorer, events, clock, config, manifests, statistics, snapshots, token budget, lifecycle, model gateway, capability attribution/analysis, provider views, dataset generators, isolation probes | Copied as-is |
| `contamination/` | preflight isolation suite (checks, models, preflight) | Copied as-is |
| `providers/` | adapter interface support: `MemoryProvider` base lives in `benchmark/providers.py`; `compliance.py` contract, `registry.py` + `registry.json`, baselines (bm25, no-memory, oracle, full-context, random), memory adapters (gbrain, mem0, hindsight, optmem) | Copied as-is; registry extended for memory providers |
| `schemas/` | JSON schemas for events, queries, ground truth, manifests, provider capabilities, result bundles | Copied as-is |
| `config/` | `default.toml`, `gateway-policy.toml`, `providers/*.toml` | Copied as-is (no secrets; api_key placeholders are empty) |
| `prompts/` | versioned reader prompts | Copied as-is |
| `scripts/` | runners, analyzers, generators, validation, environment checks | Core scripts copied; one-off forensic scripts excluded (see LEGACY) |
| `docker/` | clean-room compose patterns, gateway image, provider images | Copied as-is |
| `tests/` | unit, contract, integration suites | Copied as-is |
| `pyproject.toml`, `uv.lock`, `.python-version` | packaging | Adapted for the AMSB project name and provider extras |

### PUBLIC RESEARCH ARTIFACT (protocols, manifests, corrected reports, result summaries)

| Path | Notes |
|---|---|
| `protocols/v1/`, `protocols/capability-attribution-v1/` | Frozen protocols, preregistration, deviations, reader prompts |
| `docs/reports/` | Task 15 review, Semantic Exit original/errata/corrected, GBrain supplement, publication readiness, capability attribution v1, final publication decision |
| `docs/final-reports/` (minus four untracked synthesis files) | Consolidated report copies |
| `docs/review/` | Independent-review package and provider config summaries |
| `docs/research/` | Research landscape, Phase 0 audit, provider version log |
| `reports/protocol-v1/` | Frozen V1 result tables (controlled/native per provider) |
| `datasets/commitments/` | SHA-256 commitments proving hidden TEST packs existed before execution |
| `experiments/reader-pilot/` | Reader pilot protocol, cases, configs, dry-run/live results, hash-chain ledger (verified: no secrets, usage only) |
| `experiments/semantic-exit/README.md` | Exit experiment documentation (path-sanitized) |
| New: `reports/capability-attribution-v1/` | Sanitized analysis artifacts copied from `runs/followups/capability-attribution-v1/test/analysis/` and provider summaries/manifests |

### PUBLIC EXAMPLE (safe data for learning and reproduction)

| Path | Notes |
|---|---|
| `datasets/dev/personal/` | Public synthetic DEV corpus: events, queries, ground truth, dataset card |
| `datasets/dev/README.md` | DEV policy |
| `datasets/followups/semantic-exit-v1/` | Small public exit experiment corpus |
| `datasets/private_test/README.md` | Policy pointer; the hidden split itself is not released |

### PRIVATE / EXCLUDE

| Path | Reason |
|---|---|
| `scorer_private/` | Hidden TEST gold and private scorer material |
| `runs/` | Private run artifacts, provider state, traces (kept out of Git in the source too) |
| `.venv/` | Machine-local virtual environment |
| `.optmem/` | Pinned local OptMem install (no upstream license file) |
| `__pycache__/`, `.pytest_cache/` | Caches |
| `.env`, `*.env` | Never committed (none present) |

### LEGACY / EXCLUDE

| Path | Reason |
|---|---|
| `docs/superpowers/`, `docs/handoffs/`, `docs/progress/` | Internal agent-process documentation, not needed by AMSB |
| `docs/final-reports/*synthesis*` (4 untracked files) | Unofficial AI-model synthesis drafts, untracked in the source |
| `scripts/finalize_gbrain_correction.py`, `scripts/finalize_mem0_recovery.py`, `scripts/refine_hindsight_fidelity.py`, `scripts/attest_gbrain_local.py`, `scripts/run_gbrain_native_local.py`, `scripts/mark_provider_cleanup.py` | One-off post-freeze forensic scripts; their findings live in the corrected reports |
| `AGENTS.md` | Codex-specific working protocol; replaced by `CONTRIBUTING.md` in AMSB |

### REVIEW BEFORE RELEASE

| Path | Notes |
|---|---|
| `providers/gbrain/local_ollama.py`, `config/providers/gbrain-native-local.toml`, `tests/contract/test_gbrain_local_ollama.py` | Ollama-specific research follow-up; environment-gated, harmless, kept |
| `experiments/reader-pilot/ledger.jsonl` | Verified: usage/identity only, no request or response content |
| `docker/*/docker-compose.yml` `POSTGRES_PASSWORD` | Local-only test credential (`sovbench/sovbench`), documented as non-production |
| `providers/optmem/` | Pinned upstream has no license file; adapter documents this and is kept as an example integration |

## 2. Architectural assessment

### Question

> Can a new memory provider be added without modifying the central benchmark
> runner, scorer, metrics, datasets, or gold?

### Answer: MOSTLY (today) → YES (after a small bounded cleanup)

What already exists:

- A stable adapter contract: `MemoryProvider` ABC in `benchmark/providers.py`
  with `reset/ingest/await_ready/retrieve/snapshot/restore/stats/cleanup` plus
  optional `delete/export/import_data/restart` that raise
  `CapabilityNotSupported` honestly.
- A compliance contract (`providers/compliance.py`) with canary checks
  (current/future/cross-user/authority/deleted/read-only/snapshot/export), a
  `ProviderMeta` metadata schema, and fail-closed registration
  (`providers/registry.py`, `providers/registry.json`).
- A validation command (`scripts/check_provider.py`) used for the baseline
  providers.

What couples memory providers to central code today:

1. `scripts/run_capability_attribution.py` hardcodes `PROVIDER_COMMITS` and a
   `_provider_factory` if/elif chain for gbrain/mem0/hindsight.
2. `benchmark/capability_provider_views.py` hardcodes the native-view
   dispatch (gbrain CLI parse, mem0 search, hindsight recall).
3. The memory providers are not entries in `providers/registry.json`.

### Minimal bounded cleanup (implemented in AMSB)

1. Extend `providers/registry.json` with memory-provider entries containing
   exact upstream pins, factory module/function, and an optional native-view
   reference.
2. Add `create_provider(name, data_dir, **kwargs)` to `providers/registry.py`
   so runners construct providers by name without an if/elif chain.
3. Make `benchmark/capability_provider_views.py` consult the registry for a
   provider-specific `native_retrieve` hook first, falling back to the
   built-in views. The three researched providers keep their exact functions;
   behavior is unchanged.
4. Add `scripts/validate_provider.py` as the contributor-facing validation
   command (adapter import, reset, ingest, retrieval, deletion, native track,
   capability manifest).
5. Add a lightweight per-provider capability manifest
   (`providers/<name>/manifest.toml`) and a copyable template under
   `templates/provider/`.

### Resulting extension surface

A new Level-1/2 provider touches only:

- `providers/<name>/adapter.py`
- `providers/<name>/manifest.toml`
- `providers/registry.json` (one entry)
- `tests/contract/test_<name>_adapter.py`
- optional dependency declaration in `pyproject.toml`

A Level-3 (native-track) provider additionally implements a
`native_retrieve(provider, query, event_catalog)` hook in its adapter and
references it in the registry entry.

Central runner, scorer, metrics, datasets, gold, statistics, lifecycle, and
attribution analysis do not need changes.
