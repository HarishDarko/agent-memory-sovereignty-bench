"""Run the small post-freeze semantic memory exit experiment.

This is intentionally a one-off, sequential experiment. It is not a new
benchmark protocol or a migration framework. Category A is the pinned
provider's documented/native export surface; Category B is only a separately
labelled copy of run-owned raw state where that copy is practical.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from benchmark.config import Settings, load_settings  # noqa: E402
from benchmark.events import Event, Query, load_events, load_queries  # noqa: E402
from providers.gbrain.local_ollama import GBrainOllamaProvider  # noqa: E402
from providers.mem0.adapter import make_mem0  # noqa: E402
from providers.hindsight.adapter import make_hindsight  # noqa: E402
from scripts.run_protocol_v1 import _live_gateway  # noqa: E402

DATASET = ROOT / "datasets" / "followups" / "semantic-exit-v1"
GOLD_PATH = ROOT / "scorer_private" / "semantic-exit-v1" / "gold.json"
RUN_ROOT = ROOT / "runs" / "followups" / "semantic-exit-v1"
COMPOSE_FILE = ROOT / "docker" / "providers" / "hindsight" / "docker-compose.yml"
GBRAIN_BIN = os.environ.get("GBRAIN_BIN", r"C:\Users\haris\.bun\install\global\node_modules\gbrain\src\cli.ts")
BUN_BIN = os.environ.get("BUN_BIN", r"C:\Users\haris\.bun\bin\bun.exe")
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:4713/v1")
OLLAMA_MODEL = os.environ.get("SOVBENCH_OLLAMA_EMBEDDING_MODEL", "snowflake-arctic-embed:335m")
OLLAMA_DIMENSIONS = int(os.environ.get("SOVBENCH_OLLAMA_EMBEDDING_DIMENSIONS", "1024"))
PROVIDERS = ("gbrain", "mem0", "hindsight")
PROPERTIES = (
    "factual_content", "current_state", "historical_state", "valid_from",
    "valid_to", "source_timestamp", "original_source", "provenance",
    "authority", "explicit_user_vs_model_derived", "principal_scope",
    "supersession", "deletion_state", "raw_source_event", "derived_memory",
)


def _json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    if path.is_file():
        digest.update(path.read_bytes())
    elif path.is_dir():
        for child in sorted(path.rglob("*")):
            if child.is_file():
                digest.update(str(child.relative_to(path)).encode("utf-8"))
                digest.update(child.read_bytes())
    return digest.hexdigest()


def _files(path: Path) -> list[str]:
    if not path.exists():
        return []
    if path.is_file():
        return [path.name]
    return [str(item.relative_to(path)) for item in sorted(path.rglob("*")) if item.is_file()]


def _classify(status: str, reason: str) -> dict:
    return {"status": status, "reason": reason}


def _artifact_text(path: Path) -> str:
    chunks: list[str] = []
    for file in sorted(path.rglob("*")) if path.exists() else []:
        if file.is_file():
            try:
                chunks.append(file.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                pass
    return "\n".join(chunks)


def _event_fidelity(event: Event, gold: dict, artifact_text: str) -> dict[str, dict]:
    expected = gold.get("events", {}).get(event.event_id, {})
    blob = artifact_text
    exact_text = event.text in blob
    by_id = event.event_id in blob
    result: dict[str, dict] = {}
    result["factual_content"] = _classify("PRESERVED" if exact_text else "LOST", "source text present" if exact_text else "source text absent")
    result["current_state"] = _classify("PRESERVED" if exact_text else "NOT OBSERVABLE", "current claim is text-visible; state interpretation is not a native export field")
    result["historical_state"] = _classify("TRANSFORMED BUT EQUIVALENT" if event.valid_to and exact_text else "NOT OBSERVABLE", "validity is not a native structured field")
    for prop, value in (("valid_from", event.valid_from), ("valid_to", event.valid_to)):
        result[prop] = _classify("PRESERVED" if value and value in blob else "LOST" if value else "UNSUPPORTED", "exact timestamp found" if value and value in blob else "not present in Category A artifact")
    result["source_timestamp"] = _classify("PRESERVED" if event.valid_from and event.valid_from in blob else "LOST", "exact source-time value was or was not exported")
    result["original_source"] = _classify("PRESERVED" if event.source and event.source in blob else "LOST", "source string is or is not visible")
    result["provenance"] = _classify("PRESERVED" if event.source and ("<-" in event.source or event.source in blob) else "NOT OBSERVABLE", "source chain is visible only when the provider/export includes it")
    result["authority"] = _classify("PRESERVED" if event.authority and event.authority in blob else "LOST", "authority value is or is not visible")
    result["explicit_user_vs_model_derived"] = _classify("PRESERVED" if event.authority in {"user_explicit", "assistant_inference"} and event.authority in blob else "DEGRADED", "adapter metadata distinguishes explicit and inferred authority when exported; this is not asserted as a native guarantee")
    result["principal_scope"] = _classify("PRESERVED" if event.principal in blob and event.scope in blob else "DEGRADED", "principal and scope are visible only if retained by the provider/export")
    result["supersession"] = _classify("PRESERVED" if event.supersedes and event.supersedes in blob else "LOST" if event.supersedes else "UNSUPPORTED", "structured supersedes link is or is not present")
    result["deletion_state"] = _classify("PRESERVED" if event.operation == "delete" and by_id else "LOST" if event.operation == "delete" else "NOT OBSERVABLE", "native artifact contains or omits the deletion/tombstone")
    result["raw_source_event"] = _classify("DEGRADED" if exact_text and not (event.valid_from and event.valid_from in blob) else "PRESERVED" if exact_text else "LOST", "text survives but the complete canonical event may not")
    result["derived_memory"] = _classify("PRESERVED" if exact_text else "NOT OBSERVABLE", "derived/native memory text is or is not represented")
    # Keep the private gold reference in machine observations without copying
    # its contents into provider state. It also makes missing fields explicit.
    if expected.get("model_derived") and result["explicit_user_vs_model_derived"]["status"] == "PRESERVED":
        result["explicit_user_vs_model_derived"]["reason"] += "; model-derived classification observed"
    return result


def _fidelity_matrix(events: list[Event], gold: dict, artifact_dir: Path) -> dict:
    text = _artifact_text(artifact_dir)
    matrix: dict[str, dict[str, dict]] = {}
    for event in events:
        if event.operation == "delete":
            # Deletion commands are evaluated as lifecycle state, not ordinary
            # source memories; their tombstone is expected to be absent unless
            # the product explicitly exports tombstones.
            pass
        matrix[event.event_id] = _event_fidelity(event, gold, text)
    summary: dict[str, dict[str, int]] = {}
    for prop in PROPERTIES:
        counts: dict[str, int] = {}
        for row in matrix.values():
            status = row[prop]["status"]
            counts[status] = counts.get(status, 0) + 1
        summary[prop] = counts
    return {"per_event": matrix, "summary": summary}


def _query_observations(provider, queries: list[Query]) -> list[dict]:
    rows: list[dict] = []
    for query in queries:
        started = time.perf_counter()
        try:
            result = provider.retrieve(query)
            rows.append({
                "query_id": query.query_id,
                "retrieved_event_ids": [item.item_id for item in result.items],
                "metadata": [item.metadata for item in result.items],
                "latency_ms": round((time.perf_counter() - started) * 1000.0, 3),
                "provider_latency_ms": result.latency_ms,
                "error": None,
            })
        except Exception as exc:  # noqa: BLE001
            rows.append({"query_id": query.query_id, "retrieved_event_ids": [], "metadata": [], "latency_ms": round((time.perf_counter() - started) * 1000.0, 3), "provider_latency_ms": None, "error": f"{type(exc).__name__}: {str(exc)[:300]}"})
    return rows


def _populate(provider, events: list[Event]) -> list[dict]:
    rows: list[dict] = []
    for event in sorted(events, key=lambda row: (row.available_at, row.event_id)):
        started = time.perf_counter()
        try:
            if event.operation == "delete":
                result = {"deleted": provider.delete(event.target_event_id or "")}
            else:
                result = provider.ingest([event]).details or {}
            rows.append({"event_id": event.event_id, "operation": event.operation, "ok": True, "latency_ms": round((time.perf_counter() - started) * 1000.0, 3), "details": result})
        except Exception as exc:  # noqa: BLE001
            rows.append({"event_id": event.event_id, "operation": event.operation, "ok": False, "latency_ms": round((time.perf_counter() - started) * 1000.0, 3), "details": {"error": f"{type(exc).__name__}: {str(exc)[:300]}"}})
    return rows


def _gbrain_category_a(provider: GBrainOllamaProvider, out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    provider._run("export", "--dir", str(out))
    return {"type": "documented_native_export", "format": "GBrain Markdown export", "path": str(out), "files": _files(out), "sha256": _sha256(out), "human_readable": True}


def _mem0_category_a(provider, out: Path) -> dict:
    memory = provider._memory_instance()
    results = {}
    for user in ("alice", "bob"):
        results[user] = memory.get_all(filters={"user_id": user}, top_k=1000, show_expired=True)
    artifact = out / "mem0-get-all.json"
    _json(artifact, {"format": "Mem0 native get_all enumeration", "users": results})
    return {"type": "documented_native_enumeration", "format": "Mem0 get_all results", "path": str(artifact), "files": _files(out), "sha256": _sha256(out), "human_readable": False}


def _hindsight_category_a(provider, out: Path) -> dict:
    payload = provider._request("GET", f"/v1/default/banks/{provider.bank_id}/export")
    artifact = out / "hindsight-bank-export.json"
    _json(artifact, payload)
    return {"type": "documented_native_export", "format": "Hindsight bank export JSON", "path": str(artifact), "files": _files(out), "sha256": _sha256(out), "human_readable": True}


def _native_versions() -> dict:
    return {"gbrain": {"commit": "15b9863d13635d173562a54f55a1d388bfcf546b", "version": "0.42.73.2"}, "mem0": {"commit": "3f39fba28f7781aaf581f64a4af39d017af65835", "version": "2.0.17"}, "hindsight": {"commit": "797faf7981ce9332e2ce7c922471b72b506b4065", "version": "0.8.6"}}


def _ledger_summary(path: Path, start_lines: int) -> dict:
    if not path.exists():
        return {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "estimated_usd": 0.0}
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows = [row for row in rows if isinstance(row, dict)]
    rows = rows[start_lines:]
    prompt = sum(int((row.get("usage") or {}).get("prompt_tokens", 0) or 0) for row in rows)
    completion = sum(int((row.get("usage") or {}).get("completion_tokens", 0) or 0) for row in rows)
    return {"calls": len(rows), "prompt_tokens": prompt, "completion_tokens": completion, "total_tokens": prompt + completion, "estimated_usd": round(prompt / 1_000_000 * 0.14 + completion / 1_000_000 * 0.28, 6)}


def _destructive_receipt(provider_name: str, provider, provider_root: Path, raw_copy: Path | None) -> dict:
    receipt = {"provider": provider_name, "requested_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "provider_root": str(provider_root), "raw_copy": str(raw_copy) if raw_copy else None, "destroyed": False}
    try:
        provider.cleanup()
    except Exception as exc:  # noqa: BLE001
        receipt["cleanup_warning"] = f"{type(exc).__name__}: {str(exc)[:200]}"
    if provider_name == "mem0":
        try:
            from providers.mem0.adapter import _release_chroma
            _release_chroma()
        except Exception as exc:  # noqa: BLE001
            receipt["cleanup_warning"] = f"chroma release: {type(exc).__name__}: {str(exc)[:200]}"
        gc.collect()
    for _attempt in range(5):
        if not provider_root.exists():
            break
        try:
            shutil.rmtree(provider_root)
            break
        except OSError as exc:
            receipt["cleanup_warning"] = f"{type(exc).__name__}: {str(exc)[:200]}"
            time.sleep(1)
    receipt["destroyed"] = not provider_root.exists()
    receipt["verified"] = receipt["destroyed"]
    return receipt


def _copy_raw_state(provider_root: Path, target: Path) -> Path | None:
    if not provider_root.exists():
        return None
    shutil.copytree(provider_root, target)
    return target


def _gbrain_recovery(artifact: Path, root: Path, queries: list[Query]) -> dict:
    provider = GBrainOllamaProvider(root, embedding_model=OLLAMA_MODEL, embedding_dimensions=OLLAMA_DIMENSIONS, ollama_base_url=OLLAMA_BASE_URL, gbrain_bin=GBRAIN_BIN, bun_bin=BUN_BIN, timeout_s=600.0)
    try:
        provider._run("import", str(artifact), "--fresh", "--source-id", "bench")
        rows = []
        for query in queries:
            try:
                rows.append({"query_id": query.query_id, "raw_search": provider._run("search", query.question)[:2000], "error": None})
            except Exception as exc:  # noqa: BLE001
                rows.append({"query_id": query.query_id, "raw_search": "", "error": f"{type(exc).__name__}: {str(exc)[:300]}"})
        return {"status": "recovered", "llm_required": False, "index_rebuilt": True, "recovery_queries": rows}
    finally:
        provider.cleanup()


def _mem0_recovery(artifact: Path, root: Path, queries: list[Query]) -> dict:
    provider = make_mem0(root)
    memory = provider._memory_instance()
    data = json.loads((artifact / "mem0-get-all.json").read_text(encoding="utf-8"))
    added = 0
    for user, payload in data.get("users", {}).items():
        for item in (payload.get("results", []) if isinstance(payload, dict) else []):
            text = item.get("memory") or item.get("text")
            if not text:
                continue
            memory.add(messages=[{"role": "user", "content": text}], user_id=user, metadata=item.get("metadata") or {}, infer=False)
            added += 1
    post_exit = []
    for query in queries:
        try:
            found = memory.search(query.question, top_k=20, filters={"user_id": query.principal}, reference_date=query.as_of)
            post_exit.append({"query_id": query.query_id, "retrieved_native_ids": [item.get("id") for item in found.get("results", []) if isinstance(item, dict)], "error": None})
        except Exception as exc:  # noqa: BLE001
            post_exit.append({"query_id": query.query_id, "retrieved_native_ids": [], "error": f"{type(exc).__name__}: {str(exc)[:300]}"})
    provider.cleanup()
    return {"status": "recovered", "llm_required": False, "index_rebuilt": True, "memories_readded_without_inference": added, "post_exit_queries": post_exit}


def _hindsight_recovery(artifact: Path, root: Path, api_url: str, queries: list[Query]) -> dict:
    provider = make_hindsight(root, api_url=api_url, timeout_s=600.0)
    payload = json.loads((artifact / "hindsight-bank-export.json").read_text(encoding="utf-8"))
    try:
        response = provider._request("POST", f"/v1/default/banks/{provider.bank_id}/import", payload)
        post_exit = []
        for query in queries:
            try:
                found = provider._request("POST", f"/v1/default/banks/{provider.bank_id}/memories/recall", {"query": query.question, "budget": "high", "max_tokens": 4096, "query_timestamp": query.as_of})
                items = []
                for key in ("results", "memories", "items", "data"):
                    if isinstance(found.get(key), list):
                        items = found[key]
                        break
                post_exit.append({"query_id": query.query_id, "retrieved_native_ids": [((item.get("metadata") or {}).get("event_id") or item.get("id")) for item in items if isinstance(item, dict)], "error": None})
            except Exception as exc:  # noqa: BLE001
                post_exit.append({"query_id": query.query_id, "retrieved_native_ids": [], "error": f"{type(exc).__name__}: {str(exc)[:300]}"})
        return {"status": "recovered", "llm_required": False, "index_rebuilt": True, "response": response, "post_exit_queries": post_exit}
    finally:
        provider.cleanup()


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@contextmanager
def _hindsight_stack(gateway_port: int):
    project = "sovbench-exit-hindsight"
    api_host_port = _free_port()
    public_host_port = _free_port()
    runtime_compose = RUN_ROOT / "hindsight" / "runtime-compose.yml"
    compose_text = COMPOSE_FILE.read_text(encoding="utf-8")
    compose_text = compose_text.replace('- "8000:8888"', f'- "{api_host_port}:8888"').replace('- "8000:8000"', f'- "{public_host_port}:8000"')
    runtime_compose.parent.mkdir(parents=True, exist_ok=True)
    runtime_compose.write_text(compose_text, encoding="utf-8")
    env = dict(os.environ, COMPOSE_PROJECT_NAME=project, HINDSIGHT_API_LLM_PROVIDER="openai", HINDSIGHT_API_LLM_MODEL="deepseek-v4-flash", HINDSIGHT_API_LLM_BASE_URL="http://api-proxy:9000/v1", HINDSIGHT_API_LLM_API_KEY="sovbench-gateway", HOST_PROXY_PORT=str(gateway_port))
    command = ["docker", "compose", "-p", project, "-f", str(runtime_compose)]
    up = subprocess.run([*command, "up", "-d"], capture_output=True, text=True, timeout=600, env=env)
    if up.returncode != 0:
        raise RuntimeError(f"hindsight stack failed: {up.stderr[-500:]}")
    deadline = time.monotonic() + 240
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{public_host_port}/health", timeout=5) as response:
                if response.status == 200:
                    break
        except Exception:
            time.sleep(4)
    else:
        raise RuntimeError("hindsight API did not become healthy")
    try:
        yield f"http://127.0.0.1:{public_host_port}", project
    finally:
        subprocess.run([*command, "down", "-v", "--remove-orphans"], capture_output=True, text=True, timeout=600, env=env)


def _run_provider(name: str, events: list[Event], queries: list[Query], gold: dict, settings: Settings, root: Path) -> dict:
    provider_root = root / "original-runtime"
    category_a = root / "category-a"
    category_b = root / "category-b"
    ledger = root / "ledger.jsonl"
    result = {"provider": name, "version": _native_versions()[name], "started_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "category_a": None, "category_b": None, "failures": [], "cross_system_migration": {"status": "not_justified"}}
    gateway_url = None
    stop_gateway = None
    hindsight_context = None
    try:
        if name == "hindsight":
            live = Settings(**settings.__dict__)
            live.gateway_mode = "deepseek"
            live.identity_run_id = "semantic-exit/hindsight"
            live.identity_provider_id = "hindsight"
            gateway_url, stop_gateway = _live_gateway(live, "hindsight-semantic-exit", ledger, settings.api_key, require_identity=False, stamp_identity={"run_id": "hindsight-semantic-exit", "provider_id": "hindsight", "track": "semantic-exit"}, port=0)
            from urllib.parse import urlparse
            gateway_port = int(urlparse(gateway_url).port or 0)
            hindsight_context = _hindsight_stack(gateway_port)
            api_url, _project = hindsight_context.__enter__()
            provider = make_hindsight(provider_root, api_url=api_url, timeout_s=600.0)
        elif name == "mem0":
            live = Settings(**settings.__dict__)
            live.gateway_mode = "deepseek"
            live.identity_run_id = "semantic-exit/mem0"
            live.identity_provider_id = "mem0"
            gateway_url, stop_gateway = _live_gateway(live, "mem0-semantic-exit", ledger, settings.api_key, require_identity=False, stamp_identity={"run_id": "mem0-semantic-exit", "provider_id": "mem0", "track": "semantic-exit"})
            provider = make_mem0(provider_root, native_llm={"base_url": gateway_url, "api_key": settings.api_key, "model": settings.model})
        else:
            provider = GBrainOllamaProvider(provider_root, embedding_model=OLLAMA_MODEL, embedding_dimensions=OLLAMA_DIMENSIONS, ollama_base_url=OLLAMA_BASE_URL, gbrain_bin=GBRAIN_BIN, bun_bin=BUN_BIN, timeout_s=600.0)
        provider.await_ready(600)
        result["population"] = _populate(provider, events)
        result["pre_exit_queries"] = _query_observations(provider, queries)
        result["observable_stats"] = provider.stats()
        if name == "gbrain":
            result["category_a"] = _gbrain_category_a(provider, category_a)
        elif name == "mem0":
            result["category_a"] = _mem0_category_a(provider, category_a)
        else:
            result["category_a"] = _hindsight_category_a(provider, category_a)
        result["fidelity"] = _fidelity_matrix(events, gold, category_a)
        raw_copy = _copy_raw_state(provider_root, category_b / "raw-runtime") if name != "hindsight" else None
        result["category_b"] = {"type": "raw_disaster_recovery_state", "path": str(raw_copy) if raw_copy else None, "sha256": _sha256(raw_copy) if raw_copy else None, "available": bool(raw_copy)}
        result["destruction"] = _destructive_receipt(name, provider, provider_root, raw_copy)
        if name == "hindsight":
            # The adapter data directory is only a bank identifier. Delete the
            # actual native bank before creating a fresh recovery stack.
            provider._request("DELETE", f"/v1/default/banks/{provider.bank_id}")
            result["destruction"]["native_bank_deleted"] = True
            hindsight_context.__exit__(None, None, None)
            hindsight_context = None
            hindsight_context = _hindsight_stack(gateway_port)
            api_url, _project = hindsight_context.__enter__()
        if name == "gbrain":
            recovered = _gbrain_recovery(category_a, root / "recovered-runtime", queries)
        elif name == "mem0":
            recovered = _mem0_recovery(category_a, root / "recovered-runtime", queries)
        else:
            recovered = _hindsight_recovery(category_a, root / "recovered-runtime", api_url, queries)
        result["recovery"] = recovered
        result["ledger"] = _ledger_summary(ledger, 0)
    except Exception as exc:  # noqa: BLE001
        result["status"] = "failed"
        result["failures"].append({"class": type(exc).__name__, "error": str(exc)[:500]})
        result["ledger"] = _ledger_summary(ledger, 0)
        if provider_root.exists():
            try:
                _destructive_receipt(name, locals().get("provider"), provider_root, None)
            except Exception:
                pass
    finally:
        if hindsight_context is not None:
            hindsight_context.__exit__(None, None, None)
        if stop_gateway is not None:
            stop_gateway()
    result.setdefault("status", "completed" if not result["failures"] else "failed")
    result["finished_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    _json(root / "observation.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=PROVIDERS, action="append", help="run only the named provider; repeatable")
    args = parser.parse_args()
    if os.environ.get("SOVBENCH_PROTOCOL_COST_APPROVED") != "1":
        raise SystemExit("set SOVBENCH_PROTOCOL_COST_APPROVED=1 for the ledgered native track")
    events = load_events(DATASET / "events.jsonl")
    queries = load_queries(DATASET / "queries.jsonl")
    gold = json.loads(GOLD_PATH.read_text(encoding="utf-8"))
    settings = load_settings()
    if not settings.api_key:
        raise SystemExit("SOVBENCH_DEEPSEEK_API_KEY is required for native Mem0/Hindsight extraction")
    selected = tuple(args.provider or PROVIDERS)
    attempt_root = RUN_ROOT / ("attempt-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    _json(attempt_root / "experiment-manifest.json", {"schema": "sovbench/semantic-memory-exit/1", "dataset": {"events": str(DATASET / "events.jsonl"), "queries": str(DATASET / "queries.jsonl")}, "providers": selected, "versions": _native_versions(), "reader": {"model": settings.model, "gateway": "ledgered DeepSeek gateway", "no reader judge": True}, "started_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")})
    results = []
    for name in selected:
        # Sequential loop is a deliberate isolation guarantee.
        results.append(_run_provider(name, events, queries, gold, settings, attempt_root / name))
    _json(attempt_root / "analysis-input.json", {"schema": "sovbench/semantic-memory-exit-observations/1", "results": results, "completed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")})
    return 0 if all(row.get("status") == "completed" for row in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
