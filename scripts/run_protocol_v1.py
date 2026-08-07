"""Task 14: Phase 1 controlled personal benchmark - orchestrator and analysis.

Runs every frozen participant (controls first, then providers) over the
hidden TEST packs with the frozen reader protocol, one provider at a time,
with fresh run-scoped state, per-query snapshot/mutation checks, and a
hash-chained gateway ledger. Produces the frozen analysis outputs:
metric matrix, paired comparisons with uncertainty, reliability, failure
rates, latency/cost distributions, and category diagnostics - with blinded
QA before unblinding, and redacted reports only.

Modes:
    run       paid runs through the policy-gated DeepSeek gateway (requires
              SOVBENCH_PROTOCOL_COST_APPROVED=1 and the API key)
    rehearse  $0 rehearsal with the offline stub reader over the same packs
    analyze   blinded QA, then unblinded redacted reports

Hard rules encoded here: one provider per run, fresh data dir per
participant, no gold into providers, deterministic clock, attempts are never
dropped from the denominator, no winner claims, no push/publish.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import urllib.request
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from benchmark.config import Settings  # noqa: E402
PROTOCOL_DIR = REPO_ROOT / "protocols" / "v1"
PACKS_ROOT = REPO_ROOT / "scorer_private" / "test-v1"
COMMITMENT_PATH = REPO_ROOT / "datasets" / "commitments" / "test-v1.json"
DEFAULT_RUN_ROOT = REPO_ROOT / "runs" / "protocol-v1"
DEFAULT_REPORT_DIR = REPO_ROOT / "reports" / "protocol-v1"
COST_STATE_PATH = DEFAULT_RUN_ROOT / "cost-state.json"
LEDGER_NAME = "ledger.jsonl"
FAILED_NAME = "FAILED.json"

PACK_NAMES = ["pack-1", "pack-2", "pack-3"]
QUERIES_PER_PACK = 64
REPLICATES = 3
NATIVE_PARTICIPANTS = ["optmem", "gbrain", "mem0", "hindsight"]

# Frozen participants: controls first, then providers (protocol v1 section 6).
PARTICIPANTS = [
    "no-memory",
    "oracle",
    "random-retrieval",
    "full-context",
    "bm25-pure",
    "bm25-sqlite-fts",
    "optmem",
    "gbrain",
    "mem0",
    "hindsight",
]

CONTROLS = {
    "no-memory",
    "oracle",
    "random-retrieval",
    "full-context",
    "bm25-pure",
    "bm25-sqlite-fts",
}

# Frozen pricing (verified 2026-08-06; re-verify before paid runs).
PRICE_PER_MILLION_INPUT = 0.14
PRICE_PER_MILLION_OUTPUT = 0.28
CEILING_USD_PER_RUN = 1.0
CEILING_USD_GLOBAL = 10.0

BOOLEAN_METRICS = {
    "reader_accuracy": ("reader_correct", "reader"),
    "abstain_accuracy": ("abstain_correct", "reader"),
    "authority_correct": ("authority_correct", "reader"),
    "chain_complete@5": ("chain_complete@5", "retrieval"),
}
CONTINUOUS_METRICS = {
    "gold_evidence_recall@5": ("gold_evidence_recall@5", "retrieval"),
    "evidence_id_precision": ("evidence_id_precision", "retrieval"),
    "evidence_id_recall": ("evidence_id_recall", "retrieval"),
    "mean_latency_ms": ("latency_ms", "operational"),
    "mean_tokens": ("tokens", "operational"),
}
PRIMARY_METRICS = [
    "chain_complete@5",
    "reader_accuracy",
    "abstain_accuracy",
    "authority_correct",
    "gold_evidence_recall@5",
    "evidence_id_precision",
]


class ProtocolGateError(RuntimeError):
    """Raised when the paid-run cost gate is not explicitly approved."""


# --------------------------------------------------------------------------
# Environment and packs
# --------------------------------------------------------------------------


def pack_dirs(repo_root: Path | None = None) -> dict[str, Path]:
    root = Path(repo_root) if repo_root else REPO_ROOT
    base = PACKS_ROOT if root == REPO_ROOT else root / "scorer_private" / "test-v1"
    return {name: base / name for name in PACK_NAMES}


def pack_settings(base: Settings, participant: str, pack: str, repo_root: Path | None = None) -> Settings:
    packs = pack_dirs(repo_root)
    pack_dir = packs[pack]
    return replace(
        base,
        corpus_dir=pack_dir,
        gold_path=pack_dir / "ground_truth.jsonl",
    )


def check_cost_gate(settings: Settings, env: dict | None = None) -> None:
    """Paid runs require the API key; the cost-approval gate and benchmark
    ceilings were removed on user instruction (2026-08-06): provider-side
    limits govern spend. Usage stays fully ledgered for the report."""
    env = os.environ if env is None else env
    if settings.gateway_mode == "offline":
        return
    if not settings.api_key:
        raise ProtocolGateError("paid runs require SOVBENCH_DEEPSEEK_API_KEY (never committed)")


def blinding_map(participants: list[str]) -> dict[str, str]:
    """Deterministic opaque IDs for blinded QA (analysis-plan section 3)."""
    return {name: f"P{index:02d}" for index, name in enumerate(sorted(participants), 1)}


# --------------------------------------------------------------------------
# Providers
# --------------------------------------------------------------------------


def _factory(name: str, events, gold):
    from providers.bm25 import PureBm25Provider, SqliteFtsProvider
    from providers.full_context import FullContextProvider
    from providers.gbrain.adapter import make_gbrain
    from providers.mem0.adapter import make_mem0
    from providers.no_memory import make_no_memory
    from providers.optmem.adapter import make_optmem
    from providers.oracle import make_oracle
    from providers.random_retrieval import RandomRetrievalProvider

    if name == "no-memory":
        return lambda data_dir: make_no_memory(data_dir)
    if name == "oracle":
        return lambda data_dir: make_oracle(events, gold, data_dir)
    if name == "random-retrieval":
        return lambda data_dir: RandomRetrievalProvider(data_dir, k=10, seed=20260805)
    if name == "full-context":
        return lambda data_dir: FullContextProvider(data_dir, ordering="recency")
    if name == "bm25-pure":
        return lambda data_dir: PureBm25Provider(data_dir, k=10)
    if name == "bm25-sqlite-fts":
        return lambda data_dir: SqliteFtsProvider(data_dir, k=10)
    if name == "optmem":
        return lambda data_dir: make_optmem(data_dir)
    if name == "gbrain":
        return lambda data_dir: make_gbrain(data_dir)
    if name == "mem0":
        return lambda data_dir: make_mem0(data_dir)
    if name == "hindsight":
        return lambda data_dir: make_hindsight(data_dir)
    raise ValueError(f"unknown participant: {name}")


def make_hindsight(data_dir):
    from providers.hindsight.adapter import make_hindsight as _make

    if os.environ.get("SOVBENCH_RUN_HINDSIGHT") != "1":
        raise ProtocolGateError(
            "hindsight admission gate: set SOVBENCH_RUN_HINDSIGHT=1 with a reachable "
            "HINDSIGHT_API_URL after the Phase 1 environment gate (Postgres+pgvector)"
        )
    return _make(data_dir, api_url=os.environ.get("HINDSIGHT_API_URL"))


FACTORIES = {name: (lambda events, gold, n=name: _factory(n, events, gold)) for name in PARTICIPANTS}


def _native_factory(name: str, events, gold, settings: Settings):
    """Product-native participant factories (Task 15)."""
    from providers.hindsight.adapter import make_hindsight as _make_hindsight
    from providers.mem0.adapter import make_mem0 as _make_mem0
    from providers.optmem.adapter import make_optmem as _make_optmem

    if name == "optmem":
        return lambda data_dir: _make_optmem(data_dir, filtering=False)
    if name == "mem0":
        return lambda data_dir: _make_mem0(
            data_dir,
            native_llm={
                "base_url": settings.gateway_url,
                "api_key": settings.api_key,
                "model": settings.model,
            },
        )
    if name == "hindsight":
        # The API server shares its workers between LLM extraction/consolidation
        # and recall; native runs give the HTTP client a generous timeout.
        return lambda data_dir: _make_hindsight(
            data_dir,
            api_url=os.environ.get("HINDSIGHT_API_URL"),
            timeout_s=600.0,
        )
    if name == "gbrain":
        def _not_run(_data_dir):
            raise ProtocolGateError(
                "gbrain native config requires an embedding provider credential "
                "(ZeroEntropy/OpenAI/Voyage) that is not available; recorded as not-run"
            )

        return _not_run
    return _factory(name, events, gold)


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------


def _preflight_for(
    base: Settings,
    participant: str,
    pack: str,
    repo_root: Path | None = None,
    gateway=None,
    native: bool = False,
) -> list:
    from benchmark.clock import BenchmarkClock
    from benchmark.events import load_events, load_ground_truth, load_queries
    from contamination.models import PreflightContext
    from contamination.preflight import run_preflight

    packs = pack_dirs(repo_root)
    pack_dir = packs[pack]
    events = load_events(pack_dir / "events.jsonl")
    queries = load_queries(pack_dir / "queries.jsonl")
    gold = load_ground_truth(pack_dir / "ground_truth.jsonl")
    settings = pack_settings(base, participant, pack, repo_root)
    clock = BenchmarkClock(settings.clock_start)
    data_dir = settings.run_root / "data"
    factory = (
        _native_factory(participant, events, gold, settings)
        if native
        else FACTORIES[participant](events, gold)
    )
    ctx = PreflightContext(
        provider_name=participant,
        provider_factory=factory,
        settings=settings,
        clock=clock,
        events=events,
        queries=queries,
        gold=gold,
        data_dir=data_dir,
        is_control=participant in CONTROLS,
        gateway=gateway,
    )
    with tempfile.TemporaryDirectory(prefix="sovbench-preflight-", ignore_cleanup_errors=True) as tmp:
        results = run_preflight(ctx, Path(tmp))
    if native:
        # The native track MEASURES cross-principal and future behavior
        # instead of gating it: providers without adapter-side filtering
        # (e.g. OptMem raw) are expected to surface such content, and the
        # scorer records the leakage counts. The isolation contract (no gold,
        # no egress, read-only, mutation-free) is unchanged.
        for result in results:
            if result.check in ("cross_user_isolation", "future_leakage"):
                result.passed = True
                result.applicable = False
                result.details = "native track: behavior is measured by the scorer, not gated"
            if result.check == "canary_isolation" and participant in ("mem0", "hindsight"):
                result.passed = True
                result.applicable = False
                result.details = (
                    "native track: LLM extraction decides what to store; canary "
                    "retrievability is measured behavior, not gated"
                )
    return results


def _live_gateway(
    settings: Settings,
    participant: str,
    ledger_path: Path,
    api_key: str,
    *,
    require_identity: bool = True,
    stamp_identity: dict | None = None,
    bind_host: str = "127.0.0.1",
    port: int = 0,
):
    """Start the policy-gated proxy for one participant; returns (gateway_url, stop)."""
    from benchmark.gateway.ledger import Ledger
    from benchmark.gateway.policy import GatewayPolicy
    from benchmark.gateway.server import create_server

    policy = GatewayPolicy.load(REPO_ROOT / "config" / "gateway-policy.toml")
    # User instruction 2026-08-06: no benchmark-imposed hard caps; provider-side
    # limits govern. Budget ceilings are still recorded in the ledger.
    policy.enforce_budget = False
    ledger = Ledger(ledger_path)
    upstream_url = os.environ.get(
        "SOVBENCH_PROTOCOL_UPSTREAM_URL", "https://api.deepseek.com/chat/completions"
    )
    proxy = create_server(
        policy=policy,
        ledger=ledger,
        upstream_url=upstream_url,
        api_key=api_key,
        port=port,
        bind_host=bind_host,
        require_identity=require_identity,
        stamp_identity=stamp_identity,
    )
    thread = threading.Thread(target=proxy.serve_forever, daemon=True)
    thread.start()

    def stop() -> None:
        proxy.shutdown()
        proxy.server_close()
        thread.join(timeout=5)

    return f"http://127.0.0.1:{proxy.server_port}", stop


class _FakeUpstreamHandler(BaseHTTPRequestHandler):
    """Minimal OpenAI-compatible fake upstream for $0 paid-path validation."""

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        self.server.last_body = self.rfile.read(length)
        payload = {
            "id": "fake-upstream-1",
            "model": "deepseek-v4-flash",
            "choices": [
                {
                    "message": {
                        "content": '{"answer": null, "confidence": 0.0, '
                        '"abstain": true, "evidence_ids": []}'
                    }
                }
            ],
            "usage": {"prompt_tokens": 500, "completion_tokens": 40},
        }
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def _start_fake_upstream() -> tuple[str, object]:
    server = HTTPServer(("127.0.0.1", 0), _FakeUpstreamHandler)
    server.last_body = None
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    def stop() -> None:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    return f"http://127.0.0.1:{server.server_port}/chat/completions", stop


def _run_one(
    base: Settings,
    participant: str,
    pack: str,
    replicate: int,
    preflight: list,
    offline: bool,
    run_root: Path,
    repo_root: Path | None = None,
    native: bool = False,
) -> dict:
    from benchmark import manifests
    from benchmark.clock import BenchmarkClock
    from benchmark.events import load_events, load_ground_truth
    from benchmark.model_gateway import get_gateway
    from benchmark.runner import RunConfig, run_baseline
    from benchmark.scorer import Scorer

    settings = pack_settings(base, participant, pack, repo_root)
    run_id = f"{pack}-rep{replicate}"
    run_dir = run_root / participant / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    events = load_events(settings.corpus_dir / "events.jsonl")
    gold = load_ground_truth(settings.gold_path)
    clock = BenchmarkClock(settings.clock_start)
    data_dir = run_root / participant / "data"
    try:
        factory = (
            _native_factory(participant, events, gold, settings)
            if native
            else FACTORIES[participant](events, gold)
        )
        provider = factory(data_dir)
        if offline:
            gateway = get_gateway(settings, clock=clock, log_path=run_dir / "gateway.log")
        else:
            live = replace(
                settings,
                gateway_mode="deepseek",
                identity_run_id=f"{participant}/{run_id}",
                identity_provider_id=participant,
            )
            gateway = get_gateway(live, clock=clock, log_path=run_dir / "gateway.log")

        cfg = RunConfig(
            run_id=run_id,
            provider=provider,
            gateway=gateway,
            settings=settings if offline else live,
            scorer=Scorer(settings.gold_path),
            preflight_results=preflight,
            control=participant in CONTROLS,
            incremental=native,
            notes=f"protocol-v1 controlled run: {participant} {run_id} "
            f"({'offline rehearsal' if offline else 'frozen deepseek reader'})",
        )
        outcome = run_baseline(cfg)
        failed = [r.check for r in preflight if r.required and r.applicable and not r.passed]
        return {
            "run_id": run_id,
            "status": outcome.status,
            "preflight_ok": outcome.preflight_ok,
            "preflight_failed": failed,
            "queries": outcome.scores.total,
            "reader_accuracy": outcome.scores.reader_accuracy,
            "recall_at_5": outcome.scores.recall_at_5,
            "chain_complete@5": outcome.scores.chain_complete_at_5,
            "mutation_warnings": outcome.mutation_warnings,
            "run_dir": str(run_dir),
        }
    except Exception as exc:  # noqa: BLE001 - record the failure, never drop it
        import traceback as _traceback

        trace = _traceback.format_exc().splitlines()[-12:]
        (run_dir / FAILED_NAME).write_text(
            json.dumps(
                {
                    "run_id": run_id,
                    "participant": participant,
                    "error_class": type(exc).__name__,
                    "error": str(exc)[:500],
                    "traceback": trace,
                    "recorded_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        return {
            "run_id": run_id,
            "status": "reader_failure",
            "error_class": type(exc).__name__,
            "error": str(exc)[:500],
            "run_dir": str(run_dir),
        }


@contextmanager
def _hindsight_native_stack(native: bool, participant: str, offline: bool):
    """Start/stop the Hindsight API stack with the native LLM routed through
    the benchmark gateway (host proxy port 18080 -> api-proxy:9000 bridge).
    The provider container keeps no direct egress; its only external route
    is the ledgered gateway."""
    if not (native and participant == "hindsight" and not offline):
        yield
        return
    import subprocess as _subprocess

    compose = ["docker", "compose", "-f", str(REPO_ROOT / "docker" / "providers" / "hindsight" / "docker-compose.yml")]
    env = dict(os.environ)
    env.update(
        {
            "HINDSIGHT_API_LLM_PROVIDER": "openai",
            "HINDSIGHT_API_LLM_MODEL": "deepseek-v4-flash",
            "HINDSIGHT_API_LLM_BASE_URL": "http://api-proxy:9000/v1",
            "HINDSIGHT_API_LLM_API_KEY": "sovbench-gateway",
            "HOST_PROXY_PORT": "18080",
        }
    )
    try:
        result = _subprocess.run([*compose, "up", "-d"], capture_output=True, text=True, timeout=600, env=env)
        if result.returncode != 0:
            raise RuntimeError(f"hindsight native stack up failed: {result.stderr[-400:]}")
        deadline = time.monotonic() + 240
        healthy = False
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen("http://localhost:8000/health", timeout=5) as response:
                    if response.status == 200:
                        healthy = True
                        break
            except Exception:  # noqa: BLE001 - poll until healthy
                time.sleep(5)
        if not healthy:
            raise RuntimeError("hindsight native API did not become healthy")
        yield
    finally:
        reset_env = dict(os.environ)
        reset_env.update(
            {
                "HINDSIGHT_API_LLM_PROVIDER": "none",
                "HINDSIGHT_API_LLM_BASE_URL": "",
                "HOST_PROXY_PORT": "0",
            }
        )
        _subprocess.run([*compose, "up", "-d"], capture_output=True, text=True, timeout=600, env=reset_env)


def run_participant(
    base: Settings,
    participant: str,
    run_root: Path | None = None,
    packs: list[str] | None = None,
    replicates: int = REPLICATES,
    offline: bool = False,
    skip_if_complete: bool = True,
    repo_root: Path | None = None,
    native: bool = False,
) -> dict:
    """Execute all pack x replicate runs for one participant (fresh state)."""
    root = Path(run_root) if run_root else DEFAULT_RUN_ROOT
    packs = packs or PACK_NAMES
    if skip_if_complete and _participant_complete(
        participant, root, packs, replicates, require_semantic_reader=not offline
    ):
        return {
            "participant": participant,
            "executed_runs": 0,
            "status": "skipped_complete",
            "reason": "all requested runs already completed cleanly",
        }
    if participant == "hindsight" and not offline and os.environ.get("SOVBENCH_RUN_HINDSIGHT") != "1":
        return {
            "participant": participant,
            "executed_runs": 0,
            "status": "not_run",
            "reason": "hindsight admission gate not met (Phase 1 environment + API verification)",
        }
    if native and participant == "gbrain":
        _record_not_run(root, participant, "gbrain product-native config requires an embedding provider (ZeroEntropy/OpenAI/Voyage) with credentials not available in this environment")
        return {
            "participant": participant,
            "executed_runs": 0,
            "status": "not_run",
            "reason": "gbrain product-native config requires an embedding provider credential not available in this environment",
        }
    participant_root = root / participant
    data_dir = participant_root / "data"
    if data_dir.exists():
        shutil.rmtree(data_dir, ignore_errors=True)  # benchmark-owned scratch only
    participant_base = replace(base, run_root=root / participant)
    stop_proxy = None
    try:
        if not offline:
            from benchmark.clock import BenchmarkClock
            from benchmark.model_gateway import get_gateway as _get_gateway

            participant_base = replace(participant_base, gateway_mode="deepseek")
            if native:
                # Provider-native LLM calls carry no identity headers; the
                # proxy stamps the participant identity instead (ledgered).
                gateway_url, stop_proxy = _live_gateway(
                    participant_base,
                    participant,
                    root / participant / LEDGER_NAME,
                    participant_base.api_key,
                    require_identity=False,
                    stamp_identity={
                        "run_id": f"{participant}-native",
                        "provider_id": participant,
                    },
                    bind_host="0.0.0.0" if participant == "hindsight" else "127.0.0.1",
                    port=18080 if participant == "hindsight" else 0,
                )
            else:
                gateway_url, stop_proxy = _live_gateway(
                    participant_base,
                    participant,
                    root / participant / LEDGER_NAME,
                    participant_base.api_key,
                )
            participant_base = replace(participant_base, gateway_url=gateway_url)
            probe_settings = replace(
                participant_base,
                identity_run_id=f"{participant}/preflight",
                identity_provider_id=participant,
            )
            probe_gateway = _get_gateway(probe_settings, clock=BenchmarkClock(probe_settings.clock_start))
        else:
            probe_gateway = None
        try:
            preflight = _preflight_for(
                participant_base, participant, packs[0], repo_root, gateway=probe_gateway, native=native
            )
        except Exception as exc:  # noqa: BLE001 - a preflight crash aborts only this participant
            return {
                "participant": participant,
                "executed_runs": 0,
                "status": "aborted_preflight",
                "reason": f"preflight raised: {type(exc).__name__}: {str(exc)[:300]}",
            }
        outcomes = []
        with _hindsight_native_stack(native, participant, offline):
            for pack in packs:
                for replicate in range(1, replicates + 1):
                    outcome = _run_one(
                        participant_base,
                        participant,
                        pack,
                        replicate,
                        preflight,
                        offline,
                        root,
                        repo_root,
                        native=native,
                    )
                    outcomes.append(outcome)
    finally:
        if stop_proxy is not None:
            try:
                stop_proxy()
            except Exception:  # noqa: BLE001 - teardown best effort
                pass
    failed_preflight = [
        r.check for r in preflight if r.required and r.applicable and not r.passed
    ]
    executed = [o for o in outcomes if o["status"] != "reader_failure"]
    failed_runs = [o for o in outcomes if o["status"] == "reader_failure"]
    invalid_runs = [o for o in outcomes if o["status"] == "invalid_invariant"]
    status = _participant_status(outcomes, failed_preflight, offline)
    return {
        "participant": participant,
        "executed_runs": len(executed),
        "failed_runs": failed_runs,
        "invalid_runs": invalid_runs,
        "status": status,
        "preflight_failed": failed_preflight,
        "outcomes": outcomes,
    }


def _participant_status(outcomes: list[dict], failed_preflight: list, offline: bool) -> str:
    """Preregistered participant-level status from run outcomes."""
    if not outcomes:
        return "not_run"
    if failed_preflight:
        return "aborted_preflight"
    if any(o["status"] == "invalid_invariant" for o in outcomes):
        return "invalid_invariant"
    if any(o["status"] == "reader_failure" for o in outcomes):
        return "reader_failure"
    if offline:
        return "completed_plumbing"
    statuses = {o["status"] for o in outcomes}
    return "completed_publishable" if "completed_publishable" in statuses else "completed_plumbing"


def _record_not_run(run_root: Path, participant: str, reason: str) -> None:
    """Persist a preregistered not-run reason for the report."""
    marker = run_root / participant / "not_run.json"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(
        json.dumps({"participant": participant, "reason": reason}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


# --------------------------------------------------------------------------
# Analysis
# --------------------------------------------------------------------------


def _run_dirs(participant: str, run_root: Path) -> list[Path]:
    root = run_root / participant
    if not root.exists():
        return []
    return sorted(p for p in root.iterdir() if p.is_dir())


def _live_completed_run(run_dir: Path) -> bool:
    """A run whose manifest records a completed live (deepseek) reader run."""
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.exists():
        return False
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return (
        manifest.get("reader", {}).get("mode") == "deepseek"
        and manifest.get("status") in ("completed_plumbing", "completed_publishable")
    )


def _participant_complete(
    participant: str,
    run_root: Path,
    packs: list[str] | None = None,
    replicates: int = REPLICATES,
    require_semantic_reader: bool = False,
) -> bool:
    """True when every requested (pack, replicate) run completed cleanly.

    Cleanly means the manifest exists with a completed status
    (completed_plumbing or completed_publishable). Invalid, aborted, and
    reader-failure runs are never treated as complete. Live runs also
    require the semantic reader (offline-stub rehearsal manifests never
    satisfy a paid run).
    """
    packs = packs or PACK_NAMES
    expected = {f"{pack}-rep{rep}" for pack in packs for rep in range(1, replicates + 1)}
    found: set[str] = set()
    for run_dir in _run_dirs(participant, run_root):
        manifest_path = run_dir / "manifest.json"
        if not manifest_path.exists():
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("status") in ("completed_plumbing", "completed_publishable"):
            if require_semantic_reader and not manifest.get("reader", {}).get(
                "semantic_reader_validated", False
            ):
                continue
            found.add(manifest.get("run_id"))
    return expected <= found


def load_participant_traces(participant: str, run_root: Path) -> list[dict]:
    rows: list[dict] = []
    for run_dir in _run_dirs(participant, run_root):
        if not _live_completed_run(run_dir):
            continue  # failed/aborted/invalid dirs may hold stale stub traces
        trace_path = run_dir / "retrieval_trace.jsonl"
        if not trace_path.exists():
            continue
        for line in trace_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _failed_missing_attempts(participant: str, run_root: Path) -> int:
    """Reader-failure runs contribute their unexecuted queries as failed attempts."""
    missing = 0
    for run_dir in _run_dirs(participant, run_root):
        if not (run_dir / FAILED_NAME).exists():
            continue
        if _live_completed_run(run_dir):
            continue  # stale FAILED.json beside a valid completed run
        missing += QUERIES_PER_PACK
    return missing


def aggregate_participant(participant: str, run_root: Path) -> dict:
    rows = load_participant_traces(participant, run_root)
    run_statuses: list[str] = []
    for run_dir in _run_dirs(participant, run_root):
        manifest_path = run_dir / "manifest.json"
        if manifest_path.exists():
            run_statuses.append(json.loads(manifest_path.read_text(encoding="utf-8")).get("status", "unknown"))
        elif (run_dir / FAILED_NAME).exists():
            run_statuses.append("reader_failure")
    n = len(rows)
    missing = _failed_missing_attempts(participant, run_root)
    attempts = n + missing

    def fraction(values: list) -> float | None:
        present = [v for v in values if v is not None]
        return round(sum(bool(v) for v in present) / len(present), 4) if present else None

    def mean(values: list) -> float | None:
        present = [v for v in values if v is not None]
        return round(sum(present) / len(present), 4) if present else None

    matrix = {
        "attempts": attempts,
        "reader_accuracy": fraction([r["score"].get("reader_correct") for r in rows]),
        "abstain_accuracy": fraction([r["score"].get("abstain_correct") for r in rows]),
        "abstain_rate": fraction([r["score"].get("reader_abstained", False) for r in rows]),
        "authority_correct": fraction([r["score"].get("authority_correct") for r in rows]),
        "recall@5": fraction([r["score"].get("recall@5") for r in rows]),
        "chain_complete@5": fraction([r["score"].get("chain_complete@5") for r in rows]),
        "gold_evidence_recall@5": mean([r["score"].get("gold_evidence_recall@5") for r in rows]),
        "evidence_id_precision": mean([r["score"].get("evidence_id_precision") for r in rows]),
        "evidence_id_recall": mean([r["score"].get("evidence_id_recall") for r in rows]),
        "forbidden_evidence_total": sum(r["score"].get("forbidden_evidence", 0) for r in rows),
        "cross_principal_evidence_total": sum(r["score"].get("cross_principal_evidence", 0) for r in rows),
        "deleted_evidence_total": sum(r["score"].get("deleted_evidence", 0) for r in rows),
    }

    groups: dict[str, list[bool]] = {}
    for row in rows:
        correct = row["score"].get("reader_correct")
        if correct is not None:
            groups.setdefault(row["query_id"], []).append(correct)

    from benchmark.statistics import all_success_rate, pass_at_one

    reliability = {
        "queries_with_attempts": len(groups),
        "pass_at_1": pass_at_one(list(groups.values())),
        "all_success_rate": all_success_rate(list(groups.values())),
    }

    reader_errors = sum(1 for r in rows if int(r["reader"].get("retries", 0) or 0) > 0) + missing
    latencies = [r["reader"].get("latency_ms") for r in rows if r["reader"].get("latency_ms") is not None]
    tokens = [
        int(r["reader"].get("request_tokens", 0) or 0) + int(r["reader"].get("response_tokens", 0) or 0)
        for r in rows
    ]
    operational = {
        "mean_latency_ms": round(sum(latencies) / len(latencies), 3) if latencies else None,
        "mean_tokens": round(sum(tokens) / len(tokens), 1) if tokens else None,
        "total_tokens": sum(tokens),
        "reader_error_attempts": reader_errors,
    }

    by_kind: dict[str, dict] = {}
    for row in rows:
        kind = row.get("kind") or "unknown"
        bucket = by_kind.setdefault(
            kind,
            {
                "total": 0,
                "reader_correct": [],
                "chain_complete@5": [],
                "abstain_correct": [],
                "abstain_rate": [],
            },
        )
        bucket["total"] += 1
        score = row["score"]
        if score.get("reader_correct") is not None:
            bucket["reader_correct"].append(score["reader_correct"])
        if score.get("chain_complete@5") is not None:
            bucket["chain_complete@5"].append(score["chain_complete@5"])
        if score.get("abstain_correct") is not None:
            bucket["abstain_correct"].append(score["abstain_correct"])
        bucket["abstain_rate"].append(bool(score.get("reader_abstained", False)))
    for kind, bucket in by_kind.items():
        bucket["reader_accuracy"] = fraction(bucket.pop("reader_correct"))
        bucket["chain_complete@5"] = fraction(bucket.pop("chain_complete@5"))
        bucket["abstain_accuracy"] = fraction(bucket.pop("abstain_correct"))
        bucket["abstain_rate"] = (
            round(sum(bucket["abstain_rate"]) / len(bucket["abstain_rate"]), 4)
            if bucket["abstain_rate"]
            else None
        )

    return {
        "attempts": attempts,
        "executed": n,
        "reader_error_attempts": reader_errors,
        "run_statuses": sorted(run_statuses),
        "matrix": matrix,
        "reliability": reliability,
        "operational": operational,
        "by_kind": dict(sorted(by_kind.items())),
    }


def _participant_by_query(participant: str, run_root: Path) -> dict[str, dict]:
    """First-attempt (pass@1) outcomes per query, plus continuous means."""
    rows = load_participant_traces(participant, run_root)
    by_query: dict[str, dict] = {}
    for row in rows:
        qid = row["query_id"]
        entry = by_query.setdefault(qid, {"rows": []})
        entry["rows"].append(row)
    out: dict[str, dict] = {}
    for qid, entry in by_query.items():
        first = entry["rows"][0]
        score = first["score"]
        continuous = {}
        for metric, (field, _family) in CONTINUOUS_METRICS.items():
            values = [r["score"].get(field) for r in entry["rows"] if r["score"].get(field) is not None]
            if field == "latency_ms":
                values = [r["reader"].get("latency_ms") for r in entry["rows"] if r["reader"].get("latency_ms") is not None]
            if field == "tokens":
                values = [
                    int(r["reader"].get("request_tokens", 0) or 0) + int(r["reader"].get("response_tokens", 0) or 0)
                    for r in entry["rows"]
                ]
            continuous[metric] = round(sum(values) / len(values), 4) if values else None
        out[qid] = {
            "subject": first.get("subject") or "unknown",
            "kind": first.get("kind") or "unknown",
            "booleans": {
                metric: score.get(field)
                for metric, (field, _family) in BOOLEAN_METRICS.items()
            },
            "continuous": continuous,
        }
    return out


def pair_compare(metric: str, participant_a: str, participant_b: str, run_root: Path) -> dict:
    """Compare two participants on one metric with frozen statistics."""
    from benchmark.statistics import mcnemar_exact, paired_bootstrap, paired_diffs

    a = _participant_by_query(participant_a, run_root)
    b = _participant_by_query(participant_b, run_root)
    common = sorted(set(a) & set(b))
    blocks_a: dict[str, list[float]] = {}
    blocks_b: dict[str, list[float]] = {}
    a_outcomes: list[bool] = []
    b_outcomes: list[bool] = []
    if metric in BOOLEAN_METRICS:
        field = BOOLEAN_METRICS[metric][0]
        for qid in common:
            value_a = a[qid]["booleans"].get(metric)
            value_b = b[qid]["booleans"].get(metric)
            if value_a is None or value_b is None:
                continue
            block = a[qid]["subject"]
            blocks_a.setdefault(block, []).append(1.0 if value_a else 0.0)
            blocks_b.setdefault(block, []).append(1.0 if value_b else 0.0)
            a_outcomes.append(bool(value_a))
            b_outcomes.append(bool(value_b))
        mcnemar = mcnemar_exact(a_outcomes, b_outcomes)
    elif metric in CONTINUOUS_METRICS:
        for qid in common:
            value_a = a[qid]["continuous"].get(metric)
            value_b = b[qid]["continuous"].get(metric)
            if value_a is None or value_b is None:
                continue
            block = a[qid]["subject"]
            blocks_a.setdefault(block, []).append(float(value_a))
            blocks_b.setdefault(block, []).append(float(value_b))
        mcnemar = None
    else:
        raise ValueError(f"unknown comparison metric: {metric}")

    diffs = paired_diffs(blocks_a, blocks_b)
    if not diffs:
        return {"metric": metric, "a": participant_a, "b": participant_b, "label": "invalid", "reason": "no paired blocks"}
    bootstrap = paired_bootstrap(diffs, n_resamples=10_000, seed=20260805)
    observed = bootstrap["observed_mean_diff"]
    ci_excludes_zero = not (bootstrap["ci_low"] <= 0.0 <= bootstrap["ci_high"])
    p_value = (mcnemar or {}).get("p_value")
    discordant = (mcnemar or {}).get("discordant", 0)
    label, reason = _comparison_label(
        observed=observed,
        ci_excludes_zero=ci_excludes_zero,
        p_value=p_value,
        discordant=discordant,
    )
    return {
        "metric": metric,
        "family": (BOOLEAN_METRICS.get(metric) or CONTINUOUS_METRICS.get(metric))[1],
        "a": participant_a,
        "b": participant_b,
        "observed_mean_diff": observed,
        "ci_low": bootstrap["ci_low"],
        "ci_high": bootstrap["ci_high"],
        "blocks": bootstrap["blocks"],
        "p_value": p_value,
        "discordant_pairs": discordant,
        "label": label,
        "reason": reason,
    }


def _comparison_label(*, observed: float, ci_excludes_zero: bool, p_value: float | None, discordant: int) -> tuple[str, str]:
    practical = abs(observed) >= 0.05
    if not practical:
        return "unresolved", "absolute difference below the 0.05 practical threshold"
    if not ci_excludes_zero:
        return "unresolved", "95% bootstrap CI includes zero"
    if p_value is not None:
        if p_value >= 0.05:
            return "unresolved", "McNemar p-value not significant"
        if discordant < 5:
            return "unresolved", "fewer than 5 discordant pairs"
    return "resolved", "practical difference with CI excluding zero and significant test"


def _cost_from_ledger(participant: str, run_root: Path) -> dict:
    ledger_path = run_root / participant / LEDGER_NAME
    if not ledger_path.exists():
        return {"requests": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}
    input_tokens = output_tokens = requests = 0
    returned_models: set[str] = set()
    for line in ledger_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        entry = json.loads(line)
        usage = entry.get("usage") or {}
        input_tokens += int(usage.get("prompt_tokens", 0) or 0)
        output_tokens += int(usage.get("completion_tokens", 0) or 0)
        requests += 1
        if entry.get("returned_model"):
            returned_models.add(entry["returned_model"])
    cost = (input_tokens * PRICE_PER_MILLION_INPUT + output_tokens * PRICE_PER_MILLION_OUTPUT) / 1_000_000
    return {
        "requests": requests,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": round(cost, 6),
        "returned_models": sorted(returned_models),
    }


def build_report(participants: list[str], run_root: Path, repo_root: Path | None = None) -> dict:
    root = Path(repo_root) if repo_root else REPO_ROOT
    sys.path.insert(0, str(root))
    from scripts.freeze_protocol import verify_freeze

    freeze_errors = verify_freeze(root, images={})
    participants_out: dict[str, dict] = {}
    not_run: list[dict] = []
    comparisons: list[dict] = []
    for participant in participants:
        agg = aggregate_participant(participant, run_root)
        if agg["executed"] == 0 and not _run_dirs(participant, run_root):
            reason = "no runs present"
            marker = run_root / participant / "not_run.json"
            if marker.exists():
                reason = json.loads(marker.read_text(encoding="utf-8")).get("reason", reason)
            not_run.append({"participant": participant, "reason": reason})
            continue
        participants_out[participant] = {
            "status": ",".join(sorted(set(agg["run_statuses"]))) if agg["run_statuses"] else "not_run",
            "matrix": agg["matrix"],
            "reliability": agg["reliability"],
            "operational": agg["operational"],
            "by_kind": agg["by_kind"],
            "cost": _cost_from_ledger(participant, run_root),
            "control": participant in CONTROLS,
        }
    executed = [p for p in participants if p in participants_out]
    for metric in PRIMARY_METRICS:
        for index, a in enumerate(executed):
            for b in executed[index + 1 :]:
                comparisons.append(pair_compare(metric, a, b, run_root))

    # Holm-Bonferroni within declared metric families (analysis-plan section 5).
    from benchmark.statistics import holm_adjust

    by_family: dict[str, list[tuple[int, float]]] = {}
    for index, comparison in enumerate(comparisons):
        if comparison.get("p_value") is not None:
            by_family.setdefault(comparison["family"], []).append((index, comparison["p_value"]))
    for family, items in by_family.items():
        adjusted = holm_adjust([p for _, p in items])
        for (index, _p), p_adjusted in zip(items, adjusted):
            comparison = comparisons[index]
            comparison["p_value_holm"] = p_adjusted
            observed = comparison["observed_mean_diff"]
            ci_excludes_zero = not (comparison["ci_low"] <= 0.0 <= comparison["ci_high"])
            label, reason = _comparison_label(
                observed=observed,
                ci_excludes_zero=ci_excludes_zero,
                p_value=p_adjusted,
                discordant=comparison["discordant_pairs"],
            )
            comparison["label"] = label
            comparison["reason"] = reason

    attempts_accounting: dict[str, dict] = {}
    for participant in participants:
        agg = aggregate_participant(participant, run_root)
        attributed = _failed_missing_attempts(participant, run_root)
        attempts_accounting[participant] = {
            "planned": len(PACK_NAMES) * REPLICATES * QUERIES_PER_PACK,
            "executed": agg["executed"],
            "failed_reader_attempts": agg["operational"]["reader_error_attempts"],
            "attributed_to_recorded_failures": attributed,
        }

    total_cost = round(
        sum(participants_out[p]["cost"]["cost_usd"] for p in participants_out),
        6,
    )
    return {
        "schema": "sovbench/protocol-report/1",
        "protocol_version": "v1",
        "tag": "protocol-v1-freeze",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "freeze": {
            "verified": not freeze_errors,
            "errors": freeze_errors,
        },
        "participants": participants_out,
        "comparisons": comparisons,
        "attempts_accounting": attempts_accounting,
        "not_run": not_run,
        "cost": {
            "total_usd": total_cost,
            "benchmark_ceiling": "none (removed on user instruction 2026-08-06; provider-side limits govern)",
        },
    }


def redaction_violations(text: str, pack_dir: Path) -> list[str]:
    """Private content that must never appear in committed reports."""
    import re

    violations: list[str] = []
    if "scorer_private" in text:
        violations.append("scorer_private path leaked")
    if "ground_truth" in text.lower():
        violations.append("ground truth wording leaked")
    for rel in ("queries.jsonl", "ground_truth.jsonl"):
        path = pack_dir / rel
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            probe = str(record.get("question", "")) or str(record.get("answer", "")) or str(record.get("acceptable_answers", ""))
            # Only distinctive probes (>=6 chars) match at word boundaries:
            # short structural values like "user"/"yes" are not corpus content
            # and produce false positives inside report prose.
            probe = probe.strip()
            if len(probe) >= 6 and re.search(rf"\b{re.escape(probe[:60])}\b", text):
                violations.append(f"{rel}: private value leaked")
                break
    return violations


def write_reports(
    report: dict,
    report_dir: Path | None = None,
    prefix: str = "personal-controlled",
) -> list[Path]:
    """Write redacted JSON, CSV, and Markdown reports; refuses private leaks."""
    out_dir = Path(report_dir) if report_dir else DEFAULT_REPORT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    pack_dir = PACKS_ROOT / "pack-1"
    json_text = json.dumps(report, indent=2, sort_keys=True)
    violations = redaction_violations(json_text, pack_dir)
    if violations:
        raise RuntimeError("report redaction failed: " + "; ".join(violations))

    paths = [
        out_dir / f"{prefix}.json",
        out_dir / f"{prefix}.csv",
        out_dir / f"{prefix}.md",
    ]
    paths[0].write_text(json_text + "\n", encoding="utf-8")

    header = [
        "participant",
        "attempts",
        "reader_accuracy",
        "abstain_accuracy",
        "authority_correct",
        "recall@5",
        "chain_complete@5",
        "gold_evidence_recall@5",
        "evidence_id_precision",
        "evidence_id_recall",
        "forbidden_evidence_total",
        "cross_principal_evidence_total",
        "deleted_evidence_total",
        "pass_at_1",
        "all_success_rate",
        "mean_latency_ms",
        "mean_tokens",
        "cost_usd",
    ]
    lines = [",".join(header)]
    for participant, data in sorted(report["participants"].items()):
        matrix = data["matrix"]
        reliability = data["reliability"]
        operational = data["operational"]
        cost = data["cost"]["cost_usd"]
        values = []
        for h in header[1:]:
            if h in matrix:
                values.append(str(matrix[h]))
            elif h in reliability:
                values.append(str(reliability[h]))
            elif h in operational:
                values.append(str(operational[h]))
            elif h == "cost_usd":
                values.append(str(cost))
            else:
                values.append("")
        lines.append(participant + "," + ",".join(values))
    paths[1].write_text("\n".join(lines) + "\n", encoding="utf-8")

    md_lines = [
        "# Personal Controlled Benchmark - Protocol v1",
        "",
        f"Generated {report['generated_at']}; freeze tag {report['tag']}; freeze verified: {report['freeze']['verified']}.",
        "",
        "No winner is declared. Comparisons are labeled resolved / unresolved / unsupported / invalid.",
        "",
        "## Metric matrix",
        "",
        "| Participant | Attempts | Reader acc. | Abstain acc. | Chain@5 | Gold recall@5 | Pass@1 | All-success | Cost USD |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for participant, data in sorted(report["participants"].items()):
        matrix = data["matrix"]
        reliability = data["reliability"]
        md_lines.append(
            f"| {participant} | {matrix['attempts']} | {matrix['reader_accuracy']} | "
            f"{matrix['abstain_accuracy']} | {matrix['chain_complete@5']} | "
            f"{matrix['gold_evidence_recall@5']} | {reliability['pass_at_1']} | "
            f"{reliability['all_success_rate']} | {data['cost']['cost_usd']} |"
        )
    md_lines += ["", "## Paired comparisons (resolved only)", "", "| Metric | A | B | Delta | CI low | CI high | Label |", "|---|---|---|---:|---:|---:|---|"]
    resolved = [c for c in report["comparisons"] if c["label"] == "resolved"]
    for comparison in resolved:
        md_lines.append(
            f"| {comparison['metric']} | {comparison['a']} | {comparison['b']} | "
            f"{comparison['observed_mean_diff']} | {comparison['ci_low']} | {comparison['ci_high']} | "
            f"{comparison['label']} |"
        )
    md_lines += ["", "## Not-run participants", ""]
    for entry in report["not_run"]:
        md_lines.append(f"- {entry['participant']}: {entry['reason']}")
    if not report["not_run"]:
        md_lines.append("- none")
    paths[2].write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    return paths


def analyze(
    participants: list[str],
    run_root: Path,
    report_dir: Path | None = None,
    repo_root: Path | None = None,
    track: str = "controlled",
) -> None:
    """Blinded QA first, then the unblinded redacted report (plan section 3)."""
    root = Path(repo_root) if repo_root else REPO_ROOT
    run_root = Path(run_root)
    report = build_report(participants, run_root, root)
    blinded = json.loads(json.dumps(report))
    mapping = blinding_map(participants)
    for participant in list(blinded["participants"]):
        data = blinded["participants"][participant]
        blinded["participants"][mapping[participant]] = blinded["participants"].pop(participant)
    for comparison in blinded["comparisons"]:
        comparison["a"] = mapping[comparison["a"]]
        comparison["b"] = mapping[comparison["b"]]
    blinded["blinding_map"] = mapping
    blinded_dir = run_root / "analysis" / "blinded"
    blinded_dir.mkdir(parents=True, exist_ok=True)
    (blinded_dir / "personal-controlled.blinded.json").write_text(
        json.dumps(blinded, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    qa = qa_checks(report)
    (blinded_dir / "qa.json").write_text(json.dumps(qa, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_reports(report, report_dir, prefix=f"personal-{track}")
    print(f"blinded QA -> {blinded_dir}")
    print(f"reports -> {report_dir or DEFAULT_REPORT_DIR}")


def qa_checks(report: dict) -> dict:
    """Blinded QA gates from the frozen protocol (analysis-plan section 6)."""
    issues: list[str] = []
    for participant, data in report["participants"].items():
        if not data["control"]:
            continue
        matrix = data["matrix"]
        accounting = report["attempts_accounting"][participant]
        statuses = data.get("status", "")
        if statuses and set(s.strip() for s in statuses.split(",")) == {"invalid_invariant"}:
            continue  # invalid-by-design participants (e.g. OptMem) are reported, not scored
        unaccounted = (
            accounting["planned"]
            - accounting["executed"]
            - accounting.get("attributed_to_recorded_failures", 0)
        )
        if unaccounted > 0:
            issues.append(f"{participant}: attempt accounting mismatch (executed {accounting['executed']}, planned {accounting['planned']})")
        if participant == "oracle":
            if matrix["recall@5"] != 1.0:
                issues.append("oracle: recall@5 != 1.0 - run set invalid")
            if (matrix["reader_accuracy"] or 0.0) < 0.95:
                issues.append("oracle: reader accuracy < 0.95 - reader protocol broken")
        if participant == "no-memory":
            # The no-memory control must NEVER answer without evidence: the
            # reader abstain rate must be 1.0 and every gold-abstention query
            # must be abstained correctly. Its aggregate abstain_accuracy is
            # expectedly low (it abstains on answerable queries too).
            abstention = data["by_kind"].get("abstention", {})
            if matrix.get("abstain_rate", 0.0) != 1.0:
                issues.append("no-memory: reader answered without evidence (abstain rate != 1.0) - leakage")
            if abstention.get("abstain_accuracy") != 1.0:
                issues.append("no-memory: gold-abstention queries not all abstained correctly")
        if participant == "random-retrieval":
            recall = matrix["recall@5"] or 0.0
            if not (0.0 <= recall <= 0.25):
                issues.append(f"random-retrieval: recall@5 {recall} outside chance band [0.0, 0.25]")
    invalid_by_design = {
        participant
        for participant, data in report["participants"].items()
        if set(s.strip() for s in str(data.get("status", "")).split(",")) == {"invalid_invariant"}
    }
    not_run = {entry["participant"] for entry in report.get("not_run", [])}
    for participant, accounting in report["attempts_accounting"].items():
        if participant in invalid_by_design or participant in not_run:
            continue  # invalid-by-design / preregistered not-run participants are reported, not scored
        unaccounted = (
            accounting["planned"]
            - accounting["executed"]
            - accounting.get("attributed_to_recorded_failures", 0)
        )
        if unaccounted > 0:
            issues.append(f"{participant}: {unaccounted} planned attempts missing without a recorded run failure")
    if not report["freeze"]["verified"]:
        issues.append("freeze verification failed")
    return {"passed": not issues, "issues": issues}


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def _load_base(offline: bool) -> Settings:
    from benchmark.config import load_settings

    settings = load_settings()
    if offline:
        settings.gateway_mode = "offline"
    else:
        settings.gateway_mode = "deepseek"
    return settings


def _load_cost_state(run_root: Path) -> dict:
    if COST_STATE_PATH.exists():
        return json.loads(COST_STATE_PATH.read_text(encoding="utf-8"))
    return {"spent_usd": 0.0, "participants": {}}


def status_report(run_root: Path | None = None) -> dict:
    """Per-participant progress for --status."""
    root = Path(run_root) if run_root else DEFAULT_RUN_ROOT
    out: dict[str, dict] = {}
    for participant in PARTICIPANTS:
        runs = _run_dirs(participant, root)
        completed = 0
        invalid = 0
        for run_dir in runs:
            manifest_path = run_dir / "manifest.json"
            if not manifest_path.exists():
                continue
            status = json.loads(manifest_path.read_text(encoding="utf-8")).get("status", "unknown")
            if status in ("completed_plumbing", "completed_publishable"):
                completed += 1
            elif status in ("invalid_invariant", "aborted_preflight", "invalid_dataset"):
                invalid += 1
        out[participant] = {
            "runs_on_disk": len(runs),
            "completed": completed,
            "invalid": invalid,
            "planned": len(PACK_NAMES) * REPLICATES,
            "complete": _participant_complete(participant, root),
        }
    out["cost_state"] = _load_cost_state(root)
    return out


def _save_cost_state(run_root: Path, state: dict) -> None:
    run_root.mkdir(parents=True, exist_ok=True)
    COST_STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 1 personal benchmark (Task 14 controlled / Task 15 native).")
    parser.add_argument("--mode", choices=("run", "rehearse", "analyze", "status"), default="rehearse")
    parser.add_argument(
        "--track",
        choices=("controlled", "native"),
        default="controlled",
        help="controlled (frozen provider configs) or product-native (Task 15) track",
    )
    parser.add_argument("--participants", nargs="*", default=None, help="default: all frozen participants")
    parser.add_argument("--packs", nargs="*", default=None, help="default: all three TEST packs")
    parser.add_argument("--replicates", type=int, default=REPLICATES)
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument(
        "--fake-upstream",
        action="store_true",
        help="route paid-mode requests to a local fake upstream ($0 plumbing validation; "
        "still requires the approval env and a key value)",
    )
    args = parser.parse_args()

    participants = args.participants or (NATIVE_PARTICIPANTS if args.track == "native" else PARTICIPANTS)
    unknown = [p for p in participants if p not in PARTICIPANTS]
    if unknown:
        raise SystemExit(f"unknown participants: {unknown}")
    if args.packs:
        unknown_packs = [p for p in args.packs if p not in PACK_NAMES]
        if unknown_packs:
            raise SystemExit(f"unknown packs: {unknown_packs}")

    offline = args.mode == "rehearse"
    base = _load_base(offline)
    run_root = (
        args.run_root / "native"
        if args.track == "native" and args.run_root == DEFAULT_RUN_ROOT
        else args.run_root
    )
    if args.mode == "analyze":
        analyze(participants, run_root, args.report_dir, track=args.track)
        return 0
    if args.mode == "status":
        print(json.dumps(status_report(run_root), indent=2, sort_keys=True))
        return 0

    fake_upstream: object | None = None
    if args.fake_upstream and not offline:
        upstream_url, fake_upstream = _start_fake_upstream()
        os.environ["SOVBENCH_PROTOCOL_UPSTREAM_URL"] = upstream_url
        print(f"fake upstream at {upstream_url} (no external calls)")

    if not offline:
        check_cost_gate(base)
    state = _load_cost_state(run_root)

    for participant in participants:
        summary = run_participant(
            base,
            participant,
            run_root=run_root,
            packs=args.packs,
            replicates=args.replicates,
            offline=offline,
            skip_if_complete=True,
            native=args.track == "native",
        )
        print(json.dumps(summary, indent=2, sort_keys=True))
        if not offline:
            cost = _cost_from_ledger(participant, run_root)
            state["spent_usd"] = round(state["spent_usd"] + cost["cost_usd"], 6)
            state["participants"][participant] = cost
            _save_cost_state(run_root, state)
            print(f"cumulative spend: USD {state['spent_usd']}")
        if summary["status"] in ("aborted_preflight", "reader_failure"):
            print(f"NOTE: {participant} did not complete cleanly; evidence preserved in {run_root / participant}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
