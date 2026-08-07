#!/usr/bin/env bash
# Clean-room provider run: exactly one provider, isolated volume, no egress.
# Usage: ./scripts/cleanroom.sh <run-id> <provider-image>
set -euo pipefail

RUN_ID="${1:?usage: cleanroom.sh <run-id> <provider-image>}"
PROVIDER_IMAGE="${2:?usage: cleanroom.sh <run-id> <provider-image>}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT="sovbench-${RUN_ID}"

export PROVIDER_RUN_ID="$RUN_ID"
export PROVIDER_IMAGE
export BENCHMARK_TIME="${BENCHMARK_TIME:-2026-08-01T00:00:00Z}"

cd "$REPO_ROOT"

echo "[cleanroom] run=$RUN_ID provider=$PROVIDER_IMAGE bench_time=$BENCHMARK_TIME project=$PROJECT"
docker compose -p "$PROJECT" -f docker/compose.yml config --quiet

echo "[cleanroom] running runtime isolation probe (local images only)"
python3 scripts/verify_cleanroom.py --run-id "$RUN_ID"
echo "[cleanroom] probe passed; starting provider"

docker compose -p "$PROJECT" -f docker/compose.yml up -d provider

cleanup() {
  echo "[cleanroom] tearing down provider=$RUN_ID"
  docker compose -p "$PROJECT" -f docker/compose.yml rm -sf provider >/dev/null 2>&1 || true
  docker compose -p "$PROJECT" -f docker/compose.yml down -v >/dev/null 2>&1 || true
}
trap cleanup EXIT

# Keep the container alive for the orchestrator to drive; Ctrl-C tears it down.
sleep infinity
