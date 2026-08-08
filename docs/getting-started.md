# Getting Started with AMSB

## 1. What AMSB is

Agent Memory Sovereignty Bench (AMSB) is a provider-neutral evaluation
framework for persistent agent memory. It measures what a memory product
itself provides, what the benchmark or application provides on its behalf,
and whether lifecycle guarantees (deletion, isolation, as-of filtering,
provenance, recovery) actually hold. Its signature model attributes every
observed capability to one of five layers:

`Product -> Adapter -> Runner -> Reader -> Scorer`

## 2. What you need

Core requirements (smoke test and public DEV):

- Python 3.11-3.12
- [uv](https://docs.astral.sh/uv/)
- Git

Not required for the smoke test: paid LLM APIs, any API key, Docker, Bun,
an external memory provider, or a local embedding model. Provider
integrations add requirements of their own; see
[provider-requirements.md](provider-requirements.md).

AMSB is reader-provider neutral: the offline deterministic reader needs no
model API at all. DeepSeek V4 Flash is the frozen reference reader used for
the historical AMSB Protocol v1 model-backed experiments; a DeepSeek
configuration is required only for exact reproduction of those runs.

## 3. Five-minute local smoke test

From a fresh clone:

```bash
git clone <future-url> agent-memory-sovereignty-bench
cd agent-memory-sovereignty-bench
uv sync
uv run pytest
uv run python scripts/validate_provider.py --provider bm25-pure
uv run python scripts/run_phase0.py
```

This path requires no paid APIs, no Docker, and no external provider. `uv
sync` installs only the base dependency set; provider extras are not needed
here.

## 4. Expected successful output

Do not expect an exact test count forever; instead look for:

- `uv run pytest`: `OK (skipped=N)` with **zero failures**. Environment-gated
  provider tests may be skipped when their optional services are not
  installed; those skips are expected on a fresh clone.
- `validate_provider.py --provider bm25-pure`:

  ```text
  Provider: bm25-pure

  Adapter import        PASS
  Capability manifest   PASS
  Reset                 PASS
  Controlled ingest     PASS
  Readiness             PASS
  Controlled retrieval  PASS
  Deletion              PASS
  Native track          NOT IMPLEMENTED

  Ready for controlled DEV evaluation.
  ```

- `run_phase0.py`: each control prints
  `status=completed_plumbing preflight=PASS`, and a summary is written to
  `reports/phase0-summary.md`. Harmless notices (for example mem0's "spaCy
  is not installed" or Chroma keyword-search warnings) can appear only on
  provider paths, not on this smoke path.

A `FAIL` row, a non-zero exit, or `preflight=FAIL` means something is wrong.

## 5. Run your first public DEV benchmark

The simplest working public DEV command needs no extra dependencies:

```bash
uv run python scripts/run_provider_dev.py --provider bm25-pure
```

- Dataset: the public DEV corpus under `datasets/dev/personal/` (events,
  queries, and gold are included).
- Reader: the offline deterministic stub. No API calls, no cost.
- Results: printed per provider and written under `runs/` (gitignored) with a
  run manifest.

For a memory provider, first install its extra:

```bash
uv sync --extra mem0
uv run python scripts/run_provider_dev.py --provider mem0
```

## 6. Run an existing provider

- Mem0 OSS: [providers/mem0/README.md](../providers/mem0/README.md)
- Hindsight: [providers/hindsight/README.md](../providers/hindsight/README.md)
- GBrain: [providers/gbrain/README.md](../providers/gbrain/README.md)
- OptMem: [providers/optmem/README.md](../providers/optmem/README.md)

Every provider README records its exact tested pin, install prerequisites,
controlled/native/lifecycle support, environment variables, validation
command, and research limitations.

## 7. Add your own memory system

Follow [adding-a-provider.md](adding-a-provider.md). A Level-1 (controlled
retrieval) provider needs only its own adapter, capability manifest, config,
README, one registry entry, a contract test, and an optional dependency
extra. No central runner/scorer changes.

## 8. Common setup problems

- `uv` is not found: install uv (https://docs.astral.sh/uv/) or run it via
  `python -m uv`.
- Wrong Python version: the repo pins 3.12 in `.python-version`; uv
  installs it automatically when required.
- Tests skip provider contract tests: expected unless you install that
  provider's dependencies (`uv sync --extra mem0`, Bun + pinned GBrain CLI,
  the Hindsight Docker stack, or the pinned OptMem script).
- Windows file-lock warning during Mem0 cleanup: the validator writes
  provider scratch state under `runs/validate/` precisely to avoid temp-dir
  races; leave the directory in place while processes are stopped.

## 9. What cannot be reproduced publicly

- Hidden TEST gold and packs (`scorer_private/`): private; the published
  commitment hashes prove they existed before execution.
- Live reader results: require `SOVBENCH_DEEPSEEK_API_KEY` (paid).
- Model-backed experiments beyond the offline path require a configured
  reader; the frozen reproduction path uses the DeepSeek V4 Flash
  configuration. Any other reader is a different experimental configuration,
  not an exact reproduction of AMSB Protocol v1.
- Machine-local run artifacts under `runs/`: gitignored and not distributed.

Everything else needed to understand, run, extend, and reproduce the public
parts of the research is in this repository.
