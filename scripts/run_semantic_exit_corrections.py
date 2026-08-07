"""Run the three-provider forensic correction pass after Semantic Exit v1.

This is additive research tooling.  It never writes the original Semantic Exit
report and never changes the frozen V1 protocol or corpus.  The primary native
artifacts are collected through the pinned product surfaces; benchmark-owned
event registries are kept in a separate ignored reference file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from benchmark.config import Settings, load_settings  # noqa: E402
from benchmark.events import Event, Query, load_events, load_queries  # noqa: E402
from providers.gbrain.local_ollama import GBrainOllamaProvider  # noqa: E402
from providers.hindsight.adapter import make_hindsight  # noqa: E402
from providers.mem0.adapter import make_mem0  # noqa: E402
from scripts.run_protocol_v1 import _live_gateway  # noqa: E402
from scripts.run_semantic_memory_exit import (  # noqa: E402
    COMPOSE_FILE,
    DATASET,
    GBRAIN_BIN,
    BUN_BIN,
    GOLD_PATH,
    OLLAMA_BASE_URL,
    OLLAMA_DIMENSIONS,
    OLLAMA_MODEL,
    _copy_raw_state,
    _json,
    _ledger_summary,
    _native_versions,
    _populate,
    _query_observations,
    _sha256,
    _free_port,
)

CORRECTION_ROOT = ROOT / "runs" / "followups" / "semantic-exit-v1-correction"
GBRAIN_TIMEOUT = 600.0


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _run(command: list[str], *, env: dict[str, str] | None = None, timeout: float = 600.0) -> str:
    proc = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", timeout=timeout, env=env)
    if proc.returncode != 0:
        raise RuntimeError(f"{' '.join(command)} failed: {(proc.stderr or proc.stdout).strip()[-800:]}")
    return (proc.stdout or proc.stderr).strip()


def _gbrain_env(home: Path) -> dict[str, str]:
    env = dict(os.environ)
    env.update(
        {
            "GBRAIN_HOME": str(home),
            "OLLAMA_BASE_URL": OLLAMA_BASE_URL,
            "GBRAIN_EMBEDDING_MODEL": f"ollama:{OLLAMA_MODEL}",
            "GBRAIN_EMBEDDING_DIMENSIONS": str(OLLAMA_DIMENSIONS),
            "CI": "1",
        }
    )
    return env


def _gbrain_cli(home: Path, *args: str, timeout: float = GBRAIN_TIMEOUT) -> str:
    return _run([str(BUN_BIN), str(GBRAIN_BIN), *args], env=_gbrain_env(home), timeout=timeout)


def _gbrain_search_rows(home: Path, queries: list[Query], source_id: str) -> list[dict]:
    rows = []
    for query in queries:
        try:
            raw = _gbrain_cli(home, "search", query.question, "--source", source_id)
            rows.append({"query_id": query.query_id, "raw_search": raw[:4000], "returned": raw.count(" -- "), "error": None})
        except Exception as exc:  # noqa: BLE001
            rows.append({"query_id": query.query_id, "raw_search": "", "returned": 0, "error": f"{type(exc).__name__}: {str(exc)[:300]}"})
    return rows


def _gbrain_status(home: Path) -> dict:
    raw = _gbrain_cli(home, "sources", "status", "--json")
    return json.loads(raw)


def _copy_tree(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)


def _remove_tree(path: Path) -> bool:
    if not path.exists():
        return True
    for attempt in range(8):
        try:
            shutil.rmtree(path)
            return True
        except PermissionError:
            if attempt == 7:
                return False
            time.sleep(0.8 * (attempt + 1))
    return not path.exists()


def _fresh_gbrain_recovery(home: Path, source_path: Path, artifact_kind: str, queries: list[Query]) -> dict:
    provider = GBrainOllamaProvider(
        home,
        embedding_model=OLLAMA_MODEL,
        embedding_dimensions=OLLAMA_DIMENSIONS,
        ollama_base_url=OLLAMA_BASE_URL,
        gbrain_bin=GBRAIN_BIN,
        bun_bin=BUN_BIN,
        timeout_s=GBRAIN_TIMEOUT,
    )
    try:
        # The provider bootstrap gives us a fresh PGLite runtime.  Replace only
        # the source repository, then recreate the documented source route.
        _remove_tree(provider.brain_dir)
        _copy_tree(source_path, provider.brain_dir)
        provider._run_allow_failure("sources", "remove", "bench", "--confirm-destructive")
        provider._run("sources", "add", "bench", "--path", str(provider.brain_dir), "--force")
        provider._run("sources", "default", "bench")
        if artifact_kind == "generated_export":
            import_result = provider._run(
                "import", str(provider.brain_dir), "--fresh", "--source-id", "bench", "--json"
            )
        else:
            import_result = provider._run(
                "sync", "--repo", str(provider.brain_dir), "--source", "bench", "--no-pull", "--no-hard-deadline", "--yes"
            )
        return {
            "status": "recovered",
            "artifact_kind": artifact_kind,
            "import_or_sync_output": import_result[-4000:],
            "status_json": _gbrain_status(provider.home),
            "recovery_queries": _gbrain_search_rows(provider.home, queries, "bench"),
            "llm_required": False,
            "embedding_rebuilt": True,
            "source_registered": True,
        }
    finally:
        provider.cleanup()


def _prepare_git_repo(source: Path) -> None:
    _run(["git", "-C", str(source), "init", "-q"])
    _run(["git", "-C", str(source), "config", "user.name", "sovbench"])
    _run(["git", "-C", str(source), "config", "user.email", "sovbench@local"])
    _run(["git", "-C", str(source), "add", "-A"])
    _run(["git", "-C", str(source), "commit", "-q", "-m", "semantic exit generated export"])


def _run_gbrain(events: list[Event], queries: list[Query], root: Path) -> dict:
    original_root = root / "original-runtime"
    provider = GBrainOllamaProvider(
        original_root,
        embedding_model=OLLAMA_MODEL,
        embedding_dimensions=OLLAMA_DIMENSIONS,
        ollama_base_url=OLLAMA_BASE_URL,
        gbrain_bin=GBRAIN_BIN,
        bun_bin=BUN_BIN,
        timeout_s=GBRAIN_TIMEOUT,
    )
    result: dict = {
        "provider": "gbrain",
        "version": _native_versions()["gbrain"],
        "status": "failed",
        "failures": [],
        "source_contract": {
            "canonical": "Git/Markdown brain repository registered as a source",
            "derived": "PGLite page/chunk/embedding/search indexes rebuilt by sync or import",
            "export": "gbrain export --dir produces Markdown plus optional .raw sidecars",
            "import": "requires a fresh runtime, source registration/routing, and indexing via import/sync",
        },
    }
    try:
        provider.await_ready(GBRAIN_TIMEOUT)
        result["population"] = _populate(provider, events)
        result["pre_exit_queries"] = _query_observations(provider, queries)
        result["observable_stats"] = provider.stats()
        result["pre_exit_status_json"] = _gbrain_status(provider.home)

        canonical = root / "category-a1-canonical-brain"
        _copy_tree(provider.brain_dir, canonical)
        generated = root / "category-a2-generated-export"
        generated.mkdir(parents=True, exist_ok=True)
        export_output = provider._run("export", "--dir", str(generated))
        generated_repo = root / "generated-export-recovery-repo"
        _copy_tree(generated, generated_repo)
        _prepare_git_repo(generated_repo)
        result["category_a1"] = {"format": "canonical Git/Markdown brain repository", "path": str(canonical), "files": sorted(str(p.relative_to(canonical)) for p in canonical.rglob("*") if p.is_file()), "sha256": _sha256(canonical), "human_readable": True}
        result["category_a2"] = {"format": "gbrain export --dir Markdown artifact", "path": str(generated), "files": sorted(str(p.relative_to(generated)) for p in generated.rglob("*") if p.is_file()), "sha256": _sha256(generated), "human_readable": True, "export_output": export_output[-2000:]}

        raw_copy = _copy_raw_state(original_root, root / "category-b" / "raw-runtime")
        result["category_b"] = {"available": bool(raw_copy), "path": str(raw_copy) if raw_copy else None, "sha256": _sha256(raw_copy) if raw_copy else None, "type": "raw disaster recovery state"}
        provider.cleanup()
        result["destruction"] = {"provider_root": str(original_root), "destroyed": _remove_tree(original_root), "verified": not original_root.exists(), "retained": [str(canonical), str(generated)]}

        canonical_recovery = _fresh_gbrain_recovery(root / "recovered-canonical-runtime", canonical, "canonical", queries)
        export_recovery = _fresh_gbrain_recovery(root / "recovered-generated-runtime", generated_repo, "generated_export", queries)
        result["recovery"] = {"canonical": canonical_recovery, "generated_export": export_recovery}
        result["status"] = "completed"
    except Exception as exc:  # noqa: BLE001
        result["failures"].append({"class": type(exc).__name__, "error": str(exc)[:800]})
        result["destruction"] = {"provider_root": str(original_root), "destroyed": _remove_tree(original_root), "verified": not original_root.exists()}
    finally:
        provider.cleanup()
    _json(root / "observation.json", result)
    return result


def _zip_summary(path: Path) -> dict:
    with zipfile.ZipFile(path, "r") as archive:
        names = sorted(archive.namelist())
        manifest = json.loads(archive.read("manifest.json"))
        documents = [json.loads(archive.read(name)) for name in names if name.startswith("documents/") and name.endswith(".json")]
        return {
            "files": names,
            "manifest": manifest,
            "document_count": len(documents),
            "fact_count": sum(len(document.get("facts", [])) for document in documents),
            "observation_count": len(json.loads(archive.read("observations.json"))) if "observations.json" in names else 0,
            "documents": documents,
        }


def _hindsight_fidelity(events: list[Event], summary: dict) -> dict:
    blob = json.dumps(summary, sort_keys=True, ensure_ascii=False)
    per_event: dict[str, dict] = {}
    for event in events:
        event_id = event.event_id
        present = event_id in blob
        text_present = event.text in blob
        deleted = event.operation == "delete"
        per_event[event_id] = {
            "factual_content": "PRESERVED" if text_present else "LOST",
            "raw_source_event": "DEGRADED" if text_present else "LOST",
            "derived_memory": "PRESERVED" if text_present else "NOT OBSERVABLE",
            "original_source": "PRESERVED" if event.source and event.source in blob else "LOST",
            "provenance": "PRESERVED" if event.source and event.source in blob else "NOT OBSERVABLE",
            "authority": "PRESERVED" if event.authority and event.authority in blob else "LOST",
            "principal_scope": "PRESERVED" if event.principal in blob and event.scope in blob else "DEGRADED",
            "explicit_user_vs_model_derived": "PRESERVED" if event.authority and event.authority in blob else "DEGRADED",
            "source_timestamp": "LOST",
            "valid_from": "LOST" if event.valid_from else "UNSUPPORTED",
            "valid_to": "LOST" if event.valid_to else "UNSUPPORTED",
            "supersession": "LOST" if event.supersedes else "UNSUPPORTED",
            "deletion_state": "LOST" if deleted else "NOT OBSERVABLE",
            "current_state": "NOT OBSERVABLE",
            "historical_state": "NOT OBSERVABLE",
            "event_id_observable": "PRESERVED" if present else "LOST",
        }
    summary_counts: dict[str, dict[str, int]] = {}
    for row in per_event.values():
        for key, value in row.items():
            summary_counts.setdefault(key, {})[value] = summary_counts.setdefault(key, {}).get(value, 0) + 1
    return {"per_event": per_event, "summary": summary_counts}


@contextmanager
def _hindsight_stack(gateway_port: int, root: Path):
    project = "sovbench-semantic-correction-hindsight"
    api_host_port = _free_port()
    public_host_port = _free_port()
    compose_path = root / "hindsight" / "runtime-compose.yml"
    compose_path.parent.mkdir(parents=True, exist_ok=True)
    compose_text = COMPOSE_FILE.read_text(encoding="utf-8")
    compose_text = compose_text.replace('- "8000:8888"', f'- "{api_host_port}:8888"').replace('- "8000:8000"', f'- "{public_host_port}:8000"')
    compose_path.write_text(compose_text, encoding="utf-8")
    env = dict(os.environ, COMPOSE_PROJECT_NAME=project, HINDSIGHT_API_LLM_PROVIDER="openai", HINDSIGHT_API_LLM_MODEL="deepseek-v4-flash", HINDSIGHT_API_LLM_BASE_URL="http://api-proxy:9000/v1", HINDSIGHT_API_LLM_API_KEY="sovbench-gateway", HOST_PROXY_PORT=str(gateway_port))
    command = ["docker", "compose", "-p", project, "-f", str(compose_path)]
    up = subprocess.run([*command, "up", "-d"], capture_output=True, text=True, timeout=600, env=env)
    if up.returncode != 0:
        raise RuntimeError(f"Hindsight correction stack failed: {up.stderr[-800:]}")
    api_url = f"http://127.0.0.1:{public_host_port}"
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{api_url}/health", timeout=5) as response:
                if response.status == 200:
                    break
        except Exception:
            time.sleep(4)
    else:
        raise RuntimeError("Hindsight correction API did not become healthy")
    try:
        yield {"api_url": api_url, "project": project, "compose": compose_path, "env": env, "command": command}
    finally:
        subprocess.run([*command, "down", "-v", "--remove-orphans"], capture_output=True, text=True, timeout=600, env=env)


def _hindsight_container(info: dict) -> str:
    return _run([*info["command"], "ps", "-q", "api"], env=info["env"]).strip()


def _hindsight_admin(info: dict, *args: str) -> str:
    return _run([*info["command"], "exec", "-T", "api", "hindsight-admin", *args], env=info["env"], timeout=900)


def _run_hindsight(events: list[Event], queries: list[Query], settings: Settings, root: Path) -> dict:
    result: dict = {"provider": "hindsight", "version": _native_versions()["hindsight"], "status": "failed", "failures": [], "category": "corrected pinned whole-bank export/import"}
    ledger = root / "ledger.jsonl"
    gateway_url = None
    stop_gateway = None
    stack = None
    try:
        live = Settings(**settings.__dict__)
        live.gateway_mode = "deepseek"
        live.identity_run_id = "semantic-exit-correction/hindsight"
        live.identity_provider_id = "hindsight"
        gateway_url, stop_gateway = _live_gateway(live, "hindsight-semantic-exit-correction", ledger, settings.api_key, require_identity=False, stamp_identity={"run_id": "hindsight-semantic-exit-correction", "provider_id": "hindsight", "track": "semantic-exit-correction"}, port=0)
        gateway_port = int(urlparse(gateway_url).port or 0)
        stack = _hindsight_stack(gateway_port, root)
        info = stack.__enter__()
        provider = make_hindsight(root / "original-runtime", api_url=info["api_url"], timeout_s=900.0)
        provider.await_ready(300)
        result["population"] = _populate(provider, events)
        result["pre_exit_queries"] = _query_observations(provider, queries)
        result["observable_stats"] = provider.stats()
        bank_id = provider.bank_id
        archive_container_path = "/tmp/sovbench-semantic-correction-bank.zip"
        export_output = _hindsight_admin(info, "export-bank", "--bank", bank_id, "--output", archive_container_path)
        archive = root / "category-a" / "hindsight-bank-export.zip"
        archive.parent.mkdir(parents=True, exist_ok=True)
        _run(["docker", "cp", f"{_hindsight_container(info)}:{archive_container_path}", str(archive)], timeout=120)
        summary = _zip_summary(archive)
        _json(root / "category-a" / "hindsight-bank-export-summary.json", {k: v for k, v in summary.items() if k != "documents"})
        result["category_a"] = {"format": "hindsight-admin export-bank ZIP", "path": str(archive), "sha256": _sha256(archive), "files": summary["files"], "human_readable": True, "export_output": export_output[-3000:], "manifest": summary["manifest"], "object_counts": {"documents": summary["document_count"], "facts": summary["fact_count"], "observations": summary["observation_count"]}}
        result["fidelity"] = _hindsight_fidelity(events, summary)
        result["source_evidence"] = {"admin_commands": ["hindsight-admin export-bank --bank <id> --output <archive>", "hindsight-admin import-bank --archive <archive> --target-bank <id>"], "import_reembeds": True, "import_reruns_llm": False, "embeddings_in_archive": False, "observations_in_archive": summary["observation_count"] > 0, "history_default": False}
        provider._request("DELETE", f"/v1/default/banks/{bank_id}")
        provider.cleanup()
        stack.__exit__(None, None, None)
        stack = None
        fresh_stack = _hindsight_stack(gateway_port, root / "recovery-runtime")
        fresh_info = fresh_stack.__enter__()
        try:
            fresh_container = _hindsight_container(fresh_info)
            _run(["docker", "cp", str(archive), f"{fresh_container}:{archive_container_path}"], timeout=120)
            import_output = _hindsight_admin(fresh_info, "import-bank", "--archive", archive_container_path, "--target-bank", bank_id)
            recovered = make_hindsight(root / "recovered-runtime", api_url=fresh_info["api_url"], timeout_s=900.0)
            recovered_queries = []
            for query in queries:
                try:
                    payload = recovered._request("POST", f"/v1/default/banks/{bank_id}/memories/recall", {"query": query.question, "budget": "high", "max_tokens": 4096, "query_timestamp": query.as_of})
                    items = []
                    for key in ("results", "memories", "items", "data"):
                        if isinstance(payload.get(key), list):
                            items = payload[key]
                            break
                    recovered_queries.append({"query_id": query.query_id, "retrieved_native_ids": [((item.get("metadata") or {}).get("event_id") or item.get("id")) for item in items if isinstance(item, dict)], "error": None})
                except Exception as exc:  # noqa: BLE001
                    recovered_queries.append({"query_id": query.query_id, "retrieved_native_ids": [], "error": f"{type(exc).__name__}: {str(exc)[:300]}"})
            recovered.cleanup()
            result["recovery"] = {"status": "recovered", "import_output": import_output[-4000:], "llm_required": False, "embeddings_regenerated": True, "indexes_rebuilt": True, "post_exit_queries": recovered_queries}
        finally:
            fresh_stack.__exit__(None, None, None)
        result["ledger"] = _ledger_summary(ledger, 0)
        result["status"] = "completed"
    except Exception as exc:  # noqa: BLE001
        result["failures"].append({"class": type(exc).__name__, "error": str(exc)[:900]})
        result["ledger"] = _ledger_summary(ledger, 0)
    finally:
        if stack is not None:
            stack.__exit__(None, None, None)
        if stop_gateway is not None:
            stop_gateway()
    _json(root / "observation.json", result)
    return result


def _mem0_maximal_artifact(provider, root: Path) -> tuple[dict, dict]:
    memory = provider._memory_instance()
    users: dict[str, list] = {}
    history_errors: list[dict] = []
    for user in ("alice", "bob"):
        payload = memory.get_all(filters={"user_id": user}, top_k=1000, show_expired=True)
        items = payload.get("results", []) if isinstance(payload, dict) else []
        rows = []
        for item in items:
            row = dict(item)
            try:
                row["history"] = memory.history(item["id"])
            except Exception as exc:  # noqa: BLE001
                row["history"] = []
                history_errors.append({"memory_id": item.get("id"), "error": f"{type(exc).__name__}: {str(exc)[:300]}"})
            rows.append(row)
        users[user] = rows
    artifact = {"format": "mem0-oss-get-all-plus-history/1", "mem0_version": "2.0.17", "interfaces": ["Memory.get_all", "Memory.history(memory_id)"], "users": users, "history_errors": history_errors}
    path = root / "category-a" / "mem0-maximal-oss-exit.json"
    _json(path, artifact)
    reference = {"format": "benchmark_augmented_reference_not_native_state", "event_memory_ids": dict(sorted(provider._event_to_memory.items())), "events": [event.to_dict() for event in provider._events]}
    _json(root / "benchmark_augmented_reference.json", reference)
    return artifact, reference


def _mem0_fidelity(artifact: dict, events: list[Event]) -> dict:
    rows = [row for items in artifact.get("users", {}).values() for row in items]
    all_text = json.dumps(artifact, sort_keys=True, ensure_ascii=False)
    history_count = sum(1 for row in rows if row.get("history"))
    return {
        "counts": {"native_memories": len(rows), "memories_with_history": history_count, "history_errors": len(artifact.get("history_errors", []))},
        "properties": {
            "factual_content": "PRESERVED for derived memory text; raw source semantics not implied",
            "raw_source_event": "LOST",
            "derived_memory": "PRESERVED",
            "original_source": "PRESERVED only where adapter-supplied event metadata remains",
            "provenance": "NOT OBSERVABLE as a native lineage contract",
            "authority": "PRESERVED only as adapter-supplied metadata",
            "explicit_user_vs_model_derived": "DEGRADED",
            "timestamps": "PRESERVED for native created_at/updated_at; source/event time is not guaranteed",
            "valid_from": "LOST",
            "valid_to": "LOST or only expiration_date when explicitly native",
            "supersession": "LOST as source-event relation",
            "history": "PRESERVED for currently enumerated memory IDs; not an export-wide history enumeration",
            "principal_scope": "PRESERVED for user_id and adapter metadata on enumerated memories",
            "deletion_tombstones": "NOT OBSERVABLE from get_all; history survives deletion internally but deleted IDs are not enumerable through documented get_all",
            "machine_readability": "PRESERVED",
            "human_readability": "PRESERVED as JSON, not narrative export",
        },
        "event_id_observations": {event.event_id: ("PRESERVED" if event.event_id in all_text else "LOST/NOT OBSERVABLE") for event in events},
    }


def _mem0_recovery(artifact: dict, root: Path, queries: list[Query]) -> dict:
    provider = make_mem0(root)
    memory = provider._memory_instance()
    added = 0
    for user, rows in artifact.get("users", {}).items():
        for item in rows:
            text = item.get("memory")
            if not text:
                continue
            metadata = item.get("metadata") or {}
            memory.add(messages=[{"role": "user", "content": text}], user_id=user, metadata=metadata, infer=False)
            added += 1
    post_exit = []
    for query in queries:
        try:
            # Mem0 OSS v2.0.17 rejects reference_date. Keep the limitation
            # explicit instead of turning an unsupported as-of call into a
            # false provider recovery failure.
            found = memory.search(query.question, top_k=20, filters={"user_id": query.principal})
            post_exit.append({"query_id": query.query_id, "retrieved_native_ids": [item.get("id") for item in found.get("results", []) if isinstance(item, dict)], "error": None, "as_of_supported": False})
        except Exception as exc:  # noqa: BLE001
            post_exit.append({"query_id": query.query_id, "retrieved_native_ids": [], "error": f"{type(exc).__name__}: {str(exc)[:300]}", "as_of_supported": False})
    provider.cleanup()
    return {"status": "recovered", "llm_required": False, "histories_recreated": False, "memory_ids_changed": True, "derived_memories_readded": added, "post_exit_queries": post_exit, "sdk_correction": "v2.0.17 OSS search has no as-of parameter"}


def _run_mem0(events: list[Event], queries: list[Query], settings: Settings, root: Path) -> dict:
    result: dict = {"provider": "mem0", "version": _native_versions()["mem0"], "status": "failed", "failures": []}
    ledger = root / "ledger.jsonl"
    gateway_url = None
    stop_gateway = None
    try:
        live = Settings(**settings.__dict__)
        live.gateway_mode = "deepseek"
        live.identity_run_id = "semantic-exit-correction/mem0"
        live.identity_provider_id = "mem0"
        gateway_url, stop_gateway = _live_gateway(live, "mem0-semantic-exit-correction", ledger, settings.api_key, require_identity=False, stamp_identity={"run_id": "mem0-semantic-exit-correction", "provider_id": "mem0", "track": "semantic-exit-correction"})
        provider = make_mem0(root / "original-runtime", native_llm={"base_url": gateway_url, "api_key": settings.api_key, "model": settings.model})
        provider.await_ready(300)
        result["population"] = _populate(provider, events)
        result["pre_exit_queries"] = _query_observations(provider, queries)
        result["observable_stats"] = provider.stats()
        artifact, reference = _mem0_maximal_artifact(provider, root)
        result["category_a"] = {"format": "Mem0 OSS get_all plus history(memory_id)", "path": str(root / "category-a" / "mem0-maximal-oss-exit.json"), "sha256": _sha256(root / "category-a" / "mem0-maximal-oss-exit.json"), "native_only": True, "history_interfaces": True, "benchmark_augmented_reference": str(root / "benchmark_augmented_reference.json")}
        result["fidelity"] = _mem0_fidelity(artifact, events)
        raw_copy = _copy_raw_state(root / "original-runtime", root / "category-b" / "raw-runtime")
        result["category_b"] = {"available": bool(raw_copy), "path": str(raw_copy) if raw_copy else None, "sha256": _sha256(raw_copy) if raw_copy else None, "type": "raw disaster recovery state"}
        provider.cleanup()
        result["destruction"] = {"provider_root": str(root / "original-runtime"), "destroyed": _remove_tree(root / "original-runtime"), "verified": not (root / "original-runtime").exists(), "retained": [str(root / "category-a" / "mem0-maximal-oss-exit.json")]}
        result["recovery"] = _mem0_recovery(artifact, root / "recovered-runtime", queries)
        result["ledger"] = _ledger_summary(ledger, 0)
        result["status"] = "completed"
    except Exception as exc:  # noqa: BLE001
        result["failures"].append({"class": type(exc).__name__, "error": str(exc)[:900]})
        result["ledger"] = _ledger_summary(ledger, 0)
    finally:
        if stop_gateway is not None:
            stop_gateway()
    _json(root / "observation.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=("gbrain", "mem0", "hindsight"), action="append")
    args = parser.parse_args()
    if os.environ.get("SOVBENCH_PROTOCOL_COST_APPROVED") != "1":
        raise SystemExit("set SOVBENCH_PROTOCOL_COST_APPROVED=1 for ledgered provider-native correction calls")
    events = load_events(DATASET / "events.jsonl")
    queries = load_queries(DATASET / "queries.jsonl")
    settings = load_settings()
    if not settings.api_key and any(name in (args.provider or ("gbrain", "mem0", "hindsight")) for name in ("mem0", "hindsight")):
        raise SystemExit("SOVBENCH_DEEPSEEK_API_KEY is required for corrected native provider runs")
    CORRECTION_ROOT.mkdir(parents=True, exist_ok=True)
    selected = tuple(args.provider or ("gbrain", "mem0", "hindsight"))
    attempt = CORRECTION_ROOT / ("attempt-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    manifest = {
        "schema": "sovbench/semantic-memory-exit-correction/1",
        "original_report_commit": "80288f5e402b9b8a20a46568e00ddd494433afd3",
        "original_followup_parent_commit": "f69ba622c74089bd285571135f99660ebe687173",
        "frozen_v1_task15_commit": "c3007f4",
        "dataset": {"events": str(DATASET / "events.jsonl"), "queries": str(DATASET / "queries.jsonl"), "event_sha256": _sha256(DATASET / "events.jsonl"), "query_sha256": _sha256(DATASET / "queries.jsonl")},
        "providers": selected,
        "versions": _native_versions(),
        "reader": {"model": settings.model, "gateway": "ledgered DeepSeek gateway for native Mem0/Hindsight only", "no reader judge": True},
        "gbrain_embedding": {"provider": "Ollama", "model": OLLAMA_MODEL, "dimensions": OLLAMA_DIMENSIONS, "base_url": OLLAMA_BASE_URL, "recovery_only": True},
        "source_evidence": {"hindsight_admin": "pinned image sovbench-hindsight:797faf7-cached / hindsight-api 0.8.6", "gbrain_source": "C:\\Users\\haris\\.bun\\install\\global\\node_modules\\gbrain\\src", "mem0_source": ".venv/Lib/site-packages/mem0"},
        "started_at": _now(),
    }
    _json(attempt / "experiment-manifest.json", manifest)
    results = []
    for name in selected:
        provider_root = attempt / name
        if name == "gbrain":
            results.append(_run_gbrain(events, queries, provider_root))
        elif name == "mem0":
            results.append(_run_mem0(events, queries, settings, provider_root))
        else:
            results.append(_run_hindsight(events, queries, settings, provider_root))
    _json(attempt / "analysis-input.json", {"schema": "sovbench/semantic-memory-exit-correction-observations/1", "results": results, "completed_at": _now()})
    _json(CORRECTION_ROOT / "latest.json", {"attempt": str(attempt), "analysis_input": str(attempt / "analysis-input.json"), "providers": [row.get("provider") for row in results], "status": {row.get("provider"): row.get("status") for row in results}})
    return 0 if all(row.get("status") == "completed" for row in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
