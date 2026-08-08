# Provider Requirements

What each AMSB path needs beyond the core requirements (Python 3.11-3.12,
uv, Git).

| Goal | Additional requirements | Notes |
|---|---|---|
| Smoke test / DEV baseline | none | offline reader, no paid APIs, no Docker, no Bun, no provider, no embeddings |
| Public DEV, any baseline (e.g. `bm25-pure`) | none | `scripts/run_provider_dev.py` |
| Mem0 OSS integration | `uv sync --extra mem0` (pins mem0ai 2.0.17, chromadb 1.5.9, fastembed 0.8.0) | local Chroma + FastEmbed; telemetry disabled; no API key |
| Hindsight integration | Docker with the pinned compose stack (`docker/providers/hindsight/docker-compose.yml`); local model cache baked into the pinned image | set `HINDSIGHT_API_URL`; controlled configuration keeps provider LLM features off |
| GBrain integration | Bun >= 1.3.10 and the pinned gbrain CLI 0.42.73.2 (`15b9863d...`) | set `GBRAIN_BIN` / `BUN_BIN`; controlled configuration uses no embedding keys |
| OptMem integration | pinned upstream script installed locally (gitignored, e.g. `.optmem/memo`) | set `SOVBENCH_OPTMEM_MEMO`; upstream has no license file; never vendored; do not publish a prebuilt image |
| Frozen/live DeepSeek reader (exact V1 reproduction or new model-backed experiments) | `SOVBENCH_DEEPSEEK_API_KEY` (+ `uv sync --extra gateway`) | paid API calls; optional - never needed for smoke, DEV, or provider work |
| Reproduce hidden TEST | not possible publicly | hidden gold and packs are private; commitment hashes are published in `datasets/commitments/` |

## Reader requirements

AMSB is reader-provider neutral. The reader is a separate evaluation layer
with its own configuration:

| Goal | Reader requirement |
|---|---|
| Install AMSB | none beyond core setup |
| Run smoke test | offline deterministic reader |
| Validate/add a provider | offline reader sufficient |
| Run public DEV plumbing | offline deterministic reader, $0 |
| Run a new model-backed experiment | a compatible configured reader (not shipped beyond the frozen reference) |
| Exactly reproduce AMSB Protocol v1 model-backed results | frozen DeepSeek V4 Flash configuration |

Only the offline deterministic reader and the frozen DeepSeek reader are
shipped. No other model-provider integrations exist.

## Environment variables

| Variable | Used by | Purpose |
|---|---|---|
| `SOVBENCH_DEEPSEEK_API_KEY` | gateway | optional; frozen/live DeepSeek reader path only (paid); not needed for smoke, DEV, or provider work |
| `SOVBENCH_PROTOCOL_UPSTREAM_URL` | gateway | optional upstream override |
| `HINDSIGHT_API_URL` | Hindsight adapter | API server URL (default `http://127.0.0.1:8000`) |
| `GBRAIN_BIN`, `BUN_BIN` | GBrain adapter | pinned CLI locations (defaults under the user home Bun install) |
| `SOVBENCH_OPTMEM_MEMO` / `OPTMEM_MEMO_PATH` | OptMem adapter | pinned local script location |
| `OLLAMA_BASE_URL`, `OLLAMA_HOST` | GBrain local-embedding follow-up only | optional, not part of the controlled configuration |

None of these are required for the smoke test. See `.env.example`.
