# Docker / WSL2 clean-room

Target execution environment (canonical plan section 7):

```text
Windows host
└── WSL2 Linux engine (dedicated Ubuntu 24.04 requires an explicit setup decision)
    ├── Python 3.12 + uv      -> benchmark orchestrator / scorer
    └── Docker
        ├── exactly ONE provider under test
        ├── provider-specific isolated volume
        ├── provider-specific internal network
        └── no uncontrolled external access
```

## Isolation policy encoded in `compose.yml`

| Requirement | Enforcement |
|---|---|
| One provider per run | single `provider` service; `PROVIDER_IMAGE` is required per run |
| No uncontrolled egress | provider on `bench-internal` (`internal: true`) only |
| Only gateway may reach the outside | `gateway` on `bench-internal` + `bench-egress` |
| No cross-provider volumes | per-run named volume `bench-<PROVIDER_RUN_ID>-data` |
| No gold in provider runtime | no repo/gold mounts; provider is read-only + tmpfs |
| Deterministic clock | `BENCHMARK_TIME` env (never wall-clock "today") |

`docker compose config` validates syntax and static policy only. It does not
prove runtime egress denial, mount isolation, or cleanup. Phase 0.5 in the
implementation plan adds runtime probes; until they pass, manifests remain
non-publishable.

## WSL2 setup (one-time)

1. Verify Docker Desktop's WSL2 Linux engine. Installing a dedicated Ubuntu
   distro is a user-approved environment change, not an autonomous benchmark
   step.
2. Inside WSL2 Ubuntu: install Docker Engine
   (https://docs.docker.com/engine/install/ubuntu/) or use Docker Desktop with
   the WSL2 backend, then verify `docker info` works inside the distro.
3. Install `uv` (https://docs.astral.sh/uv/) for the Python 3.12 orchestrator
   environment, then `uv sync` in the repo root (add `gateway` extra when
   enabling the real DeepSeek gateway).

## Phase 1 provider recipe

```bash
export PROVIDER_IMAGE=ghcr.io/owner/provider:tag
export PROVIDER_RUN_ID=2026-08-05-001
export BENCHMARK_TIME=2026-08-01T00:00:00Z
./scripts/cleanroom.sh "$PROVIDER_RUN_ID" "$PROVIDER_IMAGE"
```

The provider must be configured to reach the reader model only through
`DEEPSEEK_BASE_URL=http://gateway:8000/v1`. If a provider fundamentally cannot
operate without internet (vendor cloud, embeddings API), record that as an
operational characteristic instead of loosening the controls.
