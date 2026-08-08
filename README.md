# Agent Memory Sovereignty Bench (AMSB)

> A provider-neutral evaluation framework for persistent agent memory,
> covering controlled vs native behavior, lifecycle guarantees, recovery,
> and capability attribution.

AMSB evaluates more than retrieval recall. It measures what the memory
product itself provides, what the benchmark or application provides on its
behalf, and whether lifecycle guarantees such as deletion, isolation,
as-of filtering, provenance, and recovery actually hold.

Most memory benchmarks ask whether the right memory was retrieved. AMSB also
asks which layer supplied the capability being scored:

`Product -> Adapter -> Runner -> Reader -> Scorer`

## Why AMSB exists

Memory benchmarks typically report a recall or QA number. That number cannot
answer the questions that matter when choosing or building agent memory:

- What does the memory product itself provide?
- What does the benchmark or application provide on its behalf?
- What changes when the product's real memory-formation pipeline is enabled?
- Can future information leak into historical queries?
- Can one principal retrieve another principal's memories?
- Are scope boundaries enforced natively or by the runner?
- Does deletion actually remove evidence from bounded retrieval?
- Can a runtime be destroyed and rebuilt from retained state?
- What exactly survives export?
- Which layer supplied provenance, authority, temporal filtering, isolation,
  deletion, and answer correctness?

## The capability-attribution problem

AMSB's signature reporting model attributes every observed capability to one
of five layers:

| Layer | Role |
|---|---|
| Product | the memory system itself (storage, retrieval, native lifecycle) |
| Adapter | AMSB's provider integration (event mapping, metadata, lifecycle translation) |
| Runner | the benchmark orchestration (eligibility filtering, state checks) |
| Reader | the common stateless model that answers from evidence |
| Scorer | the deterministic private scorer that judges answers |

Core rule: **do not call a benchmark-enforced property a memory-product
capability.** A successful governance result may be implemented partly or
entirely outside the product. Every provider carries a capability manifest
that states, per capability, whether it is product-native, adapter-supplied,
runner-supplied, partial, or unsupported.

## What AMSB evaluates

- Controlled vs product-native behavior (kept separate, never merged)
- Temporal / as-of evaluation and future-information leakage
- Principal isolation and scope enforcement
- Provenance and authority-conflict resolution
- Lifecycle: ingestion, deletion, export, recovery
- Capability attribution matrix per provider
- Fail-closed invariants: state-hash equality, read-only retrieval, no gold
  access, deterministic clock
- Exact provider/version pinning and reproducible manifests
- Reader/scorer separation with a stateless common reader

## Controlled vs native evaluation

**Controlled track:** canonical AMSB events are ingested through the adapter
with normalized semantics; the benchmark applies eligibility/governance
where the protocol requires; a common reader and scorer judge the result.
Question: how does the underlying system store and retrieve evidence given
normalized memory objects?

**Native track:** raw events go through the provider's real memory pipeline
(extraction, consolidation, reflection, graph construction) with native
retrieval. Question: what does the actual product do with the same events?

Native behavior is preserved, not normalized away, and the native track is
optional per provider. See [docs/controlled-vs-native.md](docs/controlled-vs-native.md).

## Adding a new memory provider

A contributor adds a provider without modifying the central runner, scorer,
metrics, datasets, or gold:

```text
fork AMSB
   -> copy templates/provider/ to providers/<name>/
   -> implement the adapter (MemoryProvider interface)
   -> declare capabilities in manifest.toml
   -> register in providers/registry.json (one entry)
   -> run python scripts/validate_provider.py --provider <name>
   -> run controlled DEV evaluation
   -> run the native track if supported
   -> receive standard AMSB metrics and attribution output
```

Provider integration levels:

- **Level 1 - Controlled Retrieval Provider:** reset, ingest normalized
  memory, retrieve candidates.
- **Level 2 - Lifecycle/Governance Provider:** any supported subset of
  deletion, principal isolation, scope, history, export, recovery.
- **Level 3 - Product-Native Provider:** provider-native extraction,
  consolidation, native retrieval policies, optional native-view hook.

Level 1 is enough to contribute. Unsupported capabilities are declared
unsupported, never faked.

Full tutorial: [docs/adding-a-provider.md](docs/adding-a-provider.md).
Capability vocabulary: [docs/provider-capabilities.md](docs/provider-capabilities.md).

## Supported providers

Existing validated integrations (exact pins preserved from the research):

| Provider | Controlled | Native | Deletion | Principal | Scope | Export | Recovery |
|---|---|---|---|---|---|---|---|
| Mem0 OSS 2.0.17 | yes | yes | native | native | partial | partial | partial |
| Hindsight 0.8.6 | yes | yes | native | assisted | assisted | yes | yes |
| GBrain 0.42.73.2 | yes | no* | native | assisted | assisted | yes | yes |
| OptMem 1fb164c | yes | no | unsupported | assisted | assisted | partial | partial |

*GBrain native TEST was not run. A supplementary local-embedding native
configuration was evaluated on DEV but did not pass the preregistered quality
guardrail, so it did not proceed to hidden TEST. The adapter includes
local-embedding code paths as adapter capability, not as a validated research
result.

This table is integration/test coverage, not a provider quality ranking.
See [docs/provider-support.md](docs/provider-support.md) and each provider's
`manifest.toml`.

## Quick start

The full walkthrough is in [docs/getting-started.md](docs/getting-started.md);
the five-minute path is below.

```bash
git clone <future-url> agent-memory-sovereignty-bench
cd agent-memory-sovereignty-bench
uv sync
uv run pytest
```

Then the free smoke test:

```bash
uv run python scripts/validate_provider.py --provider bm25-pure
uv run python scripts/run_phase0.py
```

Expected: the validator prints `PASS` rows and `Ready for controlled DEV
evaluation.`; Phase 0 prints `status=completed_plumbing preflight=PASS` for
each control.

**No model API is required to try AMSB.** The smoke test and public DEV
workflow use an offline deterministic reader. DeepSeek V4 Flash is retained
only as the frozen reference reader for exact reproduction of the original
AMSB Protocol v1 model-backed experiments. AMSB is not tied to DeepSeek.

## Prerequisites

**Required for the smoke test and DEV baseline:**

- Python 3.11-3.12 (the repository pins 3.12 in `.python-version`)
- [uv](https://docs.astral.sh/uv/)
- Git

**Not required for the smoke test or DEV baseline (verified):**

- a paid LLM API
- an OpenAI account or key
- a DeepSeek key
- Docker
- Bun
- an external memory provider
- a local embedding model

Provider integrations add their own requirements; see
[docs/provider-requirements.md](docs/provider-requirements.md).

Provider integrations need their own dependencies:

```bash
uv sync --extra mem0     # Mem0 OSS (local Chroma + FastEmbed)
# GBrain needs the pinned gbrain CLI via Bun (see providers/gbrain/README.md)
# Hindsight needs the pinned server via Docker (see docker/providers/hindsight/)
```

## Run a local smoke test

```powershell
uv run python scripts\validate_provider.py --provider bm25-pure
uv run python scripts\run_phase0.py
```

The Phase 0 runner exercises the controls (no-memory, oracle, BM25/SQLite
FTS) with the offline deterministic reader at effectively zero cost.

## Run controlled evaluation

```powershell
uv run python scripts\run_provider_dev.py --provider mem0
```

DEV uses the public corpus under `datasets/dev/personal/`. The controlled
configuration for every provider is frozen and recorded in
`providers/<name>/config.toml`.

## Run native evaluation

Native runs use the provider's own pipeline. Refer to the provider README
and `docs/controlled-vs-native.md`; native behavior is reported separately
from controlled behavior.

## Capability Attribution Matrix

The experiment that quantifies layer attribution, its preregistration, and
the matrix are in:

- [docs/capability-attribution.md](docs/capability-attribution.md)
- [docs/reports/capability-attribution-v1.md](docs/reports/capability-attribution-v1.md)
- [reports/capability-attribution-v1/](reports/capability-attribution-v1/) (analysis artifacts)

Headline findings, stated at the precision the evidence supports:

- In the tested capability-attribution experiment, benchmark-side temporal
  eligibility filtering materially changed temporal/current-state correctness
  for GBrain and Mem0 and eliminated observed future-information leakage.
  This is the strongest load-bearing attribution result.
- In the tested native views, GBrain and Hindsight returned cross-principal
  evidence that benchmark-side principal filtering removed, while Mem0's
  tested `user_id` configuration provided product-native principal isolation.
  The assisted scope/principal cells also applied temporal eligibility
  filtering, so their correctness deltas should not be attributed solely to
  scope filtering (see [docs/scientific-audit.md](docs/scientific-audit.md)).

Benchmark results should carry layer attribution.

## Lifecycle / deletion

See [docs/lifecycle-and-deletion.md](docs/lifecycle-and-deletion.md).
Deletion is exercised through each provider's native API; adapters map
abstract delete events to that API. Unsupported deletion is recorded as
unsupported.

## Recovery / Semantic Exit

See [docs/recovery-and-portability.md](docs/recovery-and-portability.md).
Portability is reported across four separate concepts: state ownership,
same-system recoverability, semantic portability, and behavioral portability.
Same-system recovery does not imply semantic or behavioral portability, and
no cross-provider migration was executed in this research.

## Research results

- [docs/reports/](docs/reports/) - Task 15 review, Semantic Exit original,
  errata, and corrected reports, GBrain supplement, capability attribution v1
- [reports/protocol-v1/](reports/protocol-v1/) - frozen V1 result tables
- [reports/capability-attribution-v1/](reports/capability-attribution-v1/) -
  capability-attribution analysis artifacts and run manifests

## Corrections

The research trail preserves original conclusions, errata, and corrected
findings rather than rewriting history:

- [docs/research-history/README.md](docs/research-history/README.md)
- Original Semantic Exit: `docs/reports/semantic-memory-exit-v1.md`
- Errata: `docs/reports/semantic-memory-exit-v1-errata.md`
- Corrected: `docs/reports/semantic-memory-exit-v1-corrected.md`

## Reproduction

Four reproduction levels are documented in
[docs/reproduction.md](docs/reproduction.md): local smoke, public DEV,
provider integration, and research reproduction. Hidden TEST gold, live
credentials, and private run artifacts remain unavailable by design; the
published commitment hashes prove the hidden packs existed before execution.

## What AMSB is NOT

AMSB is not a universal memory leaderboard and does not identify a single
"best" memory system. Results depend on provider version, configuration,
corpus, reader model, retrieval behavior, adapter implementation, and
benchmark protocol. AMSB is not proof that a provider is superior,
universally insecure, or that memory portability is solved or unsolved.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and [docs/known-technical-debt.md](docs/known-technical-debt.md).
New provider adapters, configuration corrections, lifecycle tests, recovery
tests, attribution properties, reproducibility improvements, documentation,
and bug fixes are welcome.

## Citation

See [CITATION.cff](CITATION.cff).

## License

Apache-2.0. See [LICENSE](LICENSE) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
