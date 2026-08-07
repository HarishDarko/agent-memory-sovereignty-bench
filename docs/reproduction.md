# Reproduction

## Level 1 - Local smoke (no paid services)

```bash
uv sync
uv run pytest
uv run python scripts/run_phase0.py
```

The Phase 0 runner exercises no-memory, oracle, and BM25/SQLite FTS controls
with the offline deterministic reader. Zero API cost.

## Level 2 - Public DEV

```bash
uv run python scripts/run_provider_dev.py --provider mem0   # with --extra mem0
```

The public corpus is `datasets/dev/personal/`. DEV runs are methodology
validation, not publishable results.

## Level 3 - Provider integration

- Mem0: `uv sync --extra mem0`; local Chroma + FastEmbed, telemetry disabled.
- GBrain: pinned CLI 0.42.73.2 via Bun (see `providers/gbrain/README.md`).
- Hindsight: pinned server 0.8.6 via Docker Compose
  (`docker/providers/hindsight/docker-compose.yml`), LLM features off.
- OptMem: pinned local install (see `providers/optmem/README.md`).

Contract tests are env-gated (`SOVBENCH_RUN_GBRAIN=1`,
`SOVBENCH_RUN_MEM0=1`, `SOVBENCH_RUN_HINDSIGHT=1`) and skip cleanly when the
provider is absent.

## Level 4 - Research reproduction

Publicly reproducible parts of the frozen evidence:

- Frozen V1 tables: `reports/protocol-v1/`
- Capability Attribution v1: `reports/capability-attribution-v1/` (analysis,
  provider summaries, run manifests) plus the frozen protocol and
  preregistration in `protocols/capability-attribution-v1/`
- Semantic Exit evidence: corrected reports and the small public corpus in
  `datasets/followups/semantic-exit-v1/`

Commands for the capability-attribution TEST run are in
`docs/reports/capability-attribution-v1.md` section 22.

Not reproducible without the private material:

- hidden TEST gold and packs (`scorer_private/`) - commitment hashes in
  `datasets/commitments/` prove they existed before execution
- live DeepSeek reader calls (require `SOVBENCH_DEEPSEEK_API_KEY`)
- machine-local provider state from `runs/`

Model identity: every manifest records the requested and returned model;
the researched runs returned `deepseek-v4-flash`.
