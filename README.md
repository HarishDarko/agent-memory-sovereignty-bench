# Memory Sovereignty Benchmark

Controlled, isolated benchmark of AI memory systems. The central question is
not just "which memory has the best recall" but:

> Can an AI memory system maintain correct, authorized, erasable, evolving,
> useful, user-owned state under controlled conditions - and can that state
> survive the loss or replacement of the memory provider itself?

Canonical plan (source of truth):
[Memory Sovereignty Benchmark - Final Research & Execution Plan](https://app.notion.com/p/3b4916c73ada81f8b196e8952eed8554)

Repo-local working reference: [SPEC.md](SPEC.md).

## Status

**Phase 0 corrected (current): harness/methodology validation.** The orchestrator, model
gateway stub, private deterministic scorer, snapshot/restore, token budget,
run manifests, and the contamination preflight suite run end-to-end with three
controls only:

- no-memory (reader must abstain)
- oracle (reader receives exact gold evidence)
- BM25 / SQLite FTS baseline (how far simple retrieval gets us)

No memory systems (GBrain, OptMem, Mem0, Hindsight, ...) are installed or
benchmarked yet. API cost during Phase 0 is effectively $0: the gateway runs in
`offline` mode with a deterministic stub.

These runs are labeled `completed_plumbing` and are **not publishable benchmark
results**. Runtime container-egress and semantic-reader controls remain not
applicable until Phase 0.5, and each manifest records those gaps. See the
[Phase 0 audit](docs/research/2026-08-05-phase0-audit.md) and the
[remaining-phases plan](docs/superpowers/plans/2026-08-05-memory-sovereignty-remaining-phases.md).

## Quickstart (Windows host, Phase 0)

```powershell
uv sync --frozen
uv run --frozen python scripts\generate_dev_corpus.py
uv run --frozen python -m unittest discover -s tests -v
uv run --frozen python scripts\run_phase0.py
```

Docker Desktop's WSL2 Linux engine is the target runtime for real providers.
The Compose file currently passes static rendering, but runtime isolation is
not certified until Phase 0.5 probes pass. See
`docker/README.md` and `scripts/check_environment.py`.

## Layout

```text
benchmark/        orchestrator, gateway, scorer, snapshots, manifests, lifecycle
contamination/    preflight isolation suite
providers/        provider adapters (baselines now; memory systems in Phase 1+)
datasets/dev/     public synthetic development corpus (events, queries, gold)
datasets/private_test/  hidden test split (gitignored until release)
scorer_private/   private scorer state / hidden gold (gitignored until release)
prompts/          versioned reader prompts
docker/           WSL2/Docker clean-room pattern (one provider per run)
scripts/          corpus generator, Phase 0 runner, environment checks
tests/            harness verification suite (stdlib unittest)
runs/             per-run artifacts (manifests, traces, scores) - gitignored
reports/          aggregated summaries - gitignored
```

## Cost and isolation rules (Phase 0)

- Gateway stays in `offline` mode; the DeepSeek configuration exists but is
  only active when `SOVBENCH_GATEWAY_MODE=deepseek` and a key is supplied.
- Deterministic benchmark clock; never wall-clock "today" for scoring.
- One provider per run, per-checkpoint event replay, per-query state restore,
  and fail-closed read-only retrieval checks.
- Gold answers never enter provider state, provider containers, or prompts.
- No leaderboard result is trusted unless preflight proves the environment is
  isolated.

## Reader model identity

The planned reader uses the official `deepseek-v4-flash` API alias, whose
2026-07-31 dated release is **DeepSeek-V4-Flash-0731**. “DeepSeek V4 Plus 07-31”
is not used as a scientific identifier because no reviewed official source
defines that name. Every real run records requested and returned identity; the
current offline stub makes no DeepSeek call.

## Contributing protocol

See [AGENTS.md](AGENTS.md). The repo is a clean room: no real personal/project
files, no gold in provider paths, and no real provider installs until Phase 1.
