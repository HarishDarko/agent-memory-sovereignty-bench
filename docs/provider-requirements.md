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
| Live common reader | `SOVBENCH_DEEPSEEK_API_KEY` (+ `uv sync --extra gateway`) | paid API calls; only for live reader runs |
| Reproduce hidden TEST | not possible publicly | hidden gold and packs are private; commitment hashes are published in `datasets/commitments/` |

## Environment variables

| Variable | Used by | Purpose |
|---|---|---|
| `SOVBENCH_DEEPSEEK_API_KEY` | gateway | live reader calls (paid) |
| `SOVBENCH_PROTOCOL_UPSTREAM_URL` | gateway | optional upstream override |
| `HINDSIGHT_API_URL` | Hindsight adapter | API server URL (default `http://127.0.0.1:8000`) |
| `GBRAIN_BIN`, `BUN_BIN` | GBrain adapter | pinned CLI locations (defaults under the user home Bun install) |
| `SOVBENCH_OPTMEM_MEMO` / `OPTMEM_MEMO_PATH` | OptMem adapter | pinned local script location |
| `OLLAMA_BASE_URL`, `OLLAMA_HOST` | GBrain local-embedding follow-up only | optional, not part of the controlled configuration |

None of these are required for the smoke test. See `.env.example`.
