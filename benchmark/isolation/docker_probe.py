"""Executable clean-room runtime probe.

Proves, with locally cached images only, that a provider container has no
uncontrolled internet egress, can reach only the internal gateway, receives no
gold/private mounts, runs with the declared hardening, and that every
run-scoped container, network, and volume is removed afterwards. An
unavailable or failed probe is recorded as failed, never as passed.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from pathlib import Path

from benchmark.isolation.docker_policy import check_rendered_policy, check_static_policy

BASE_COMPOSE = "docker/compose.yml"
PROBE_COMPOSE = "docker/compose.probe.yml"
PROVIDER_IMAGE = "alpine:3.17"
GATEWAY_IMAGE = "alpine:3.17"
BENCHMARK_TIME = "2026-08-01T00:00:00Z"

EGRESS_SCRIPT = (
    "set +e\n"
    "DNS_OK=0; getent hosts api.deepseek.com >/dev/null 2>&1 && DNS_OK=1\n"
    "HTTP_OK=0; wget -T 4 -qO /dev/null http://api.deepseek.com/ 2>/dev/null && HTTP_OK=1\n"
    "HTTPS_OK=0; wget -T 4 -qO /dev/null https://api.deepseek.com/ 2>/dev/null && HTTPS_OK=1\n"
    "GW_OK=0\n"
    "for i in 1 2 3 4 5 6 7 8 9 10; do\n"
    "  if wget -T 2 -qO - http://gateway:8000/ 2>/dev/null | grep -q '^OK$'; then GW_OK=1; break; fi\n"
    "  sleep 1\n"
    "done\n"
    'echo "dns=$DNS_OK http=$HTTP_OK https=$HTTPS_OK gateway=$GW_OK"\n'
)


class ProbeError(RuntimeError):
    pass


def _run(cmd: list[str], env: dict | None = None, timeout: float = 90.0):
    process_env = dict(os.environ)
    if env:
        process_env.update(env)
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=process_env)
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def run_probe(run_id: str, repo_root: Path, out_path: Path | None = None) -> dict:
    repo_root = Path(repo_root)
    project = re.sub(r"[^A-Za-z0-9_.-]", "-", f"sovbench-probe-{run_id}")
    errors: list[str] = []
    evidence: dict = {
        "run_id": run_id,
        "project": project,
        "docker": {},
        "probes": {},
        "inspection": {},
        "cleanup": {},
        "errors": errors,
        "passed": False,
    }
    compose_env = {
        "PROVIDER_IMAGE": PROVIDER_IMAGE,
        "GATEWAY_IMAGE": GATEWAY_IMAGE,
        "PROVIDER_RUN_ID": run_id,
        "BENCHMARK_TIME": BENCHMARK_TIME,
    }
    compose = [
        "docker",
        "compose",
        "-p",
        project,
        "-f",
        str(repo_root / BASE_COMPOSE),
        "-f",
        str(repo_root / PROBE_COMPOSE),
    ]

    def run(cmd: list[str], timeout: float = 90.0, env: dict | None = None):
        try:
            return _run(cmd, env=env, timeout=timeout)
        except (subprocess.TimeoutExpired, OSError) as exc:
            errors.append(f"command failed: {' '.join(cmd)}: {exc}")
            return None

    # Version evidence.
    version = run(["docker", "version", "--format", "{{.Server.Version}}"])
    evidence["docker"]["server_version"] = version[1] if version and version[0] == 0 else "unavailable"
    compose_version = run(["docker", "compose", "version", "--short"])
    evidence["docker"]["compose_version"] = (
        compose_version[1] if compose_version and compose_version[0] == 0 else "unavailable"
    )

    # Static policy (text) and rendered policy (expanded Compose model).
    combined = (repo_root / BASE_COMPOSE).read_text(encoding="utf-8")
    combined += "\n" + (repo_root / PROBE_COMPOSE).read_text(encoding="utf-8")
    for issue in check_static_policy(combined):
        errors.append(f"static policy: {issue}")

    rendered_result = run([*compose, "config", "--format", "json"], env=compose_env)
    if rendered_result is None or rendered_result[0] != 0:
        errors.append(
            f"compose config failed: {(rendered_result[2] if rendered_result else 'no output') or 'no output'}"
        )
    else:
        rendered = json.loads(rendered_result[1])
        evidence["docker"]["rendered"] = rendered
        for issue in check_rendered_policy(rendered, probe=True):
            errors.append(f"rendered policy: {issue}")

    if errors:
        _write_evidence(evidence, out_path)
        return evidence

    # Bring up the probe stack (provider + placeholder gateway, local images).
    up = run([*compose, "up", "-d"], timeout=180, env=compose_env)
    if up is None or up[0] != 0:
        errors.append(f"probe stack failed to start: {(up[2] if up else 'no output') or 'no output'}")
        _write_evidence(evidence, out_path)
        return evidence

    try:
        provider_id = ""
        for _ in range(45):
            ps = run([*compose, "ps", "-q", "provider"], timeout=30, env=compose_env)
            if ps and ps[0] == 0 and ps[1]:
                candidate = ps[1].splitlines()[-1].strip()
                state = run(["docker", "inspect", "-f", "{{.State.Running}}", candidate], timeout=30)
                if state and state[0] == 0 and state[1].strip() == "true":
                    provider_id = candidate
                    break
            time.sleep(2)
        if not provider_id:
            errors.append("provider container did not become ready within the timeout")
            return evidence

        # Egress probe from inside the provider container.
        probe = run([*compose, "exec", "-T", "provider", "sh", "-c", EGRESS_SCRIPT], timeout=60, env=compose_env)
        if probe is None or probe[0] != 0:
            errors.append(f"egress probe exec failed: {probe}")
        else:
            match = re.search(r"dns=(\d+) http=(\d+) https=(\d+) gateway=(\d+)", probe[1])
            if not match:
                errors.append(f"unexpected egress probe output: {probe[1]!r}")
            else:
                dns, http, https, gateway = (int(value) for value in match.groups())
                evidence["probes"] = {
                    "public_dns": {
                        "allowed": bool(dns),
                        "note": "DNS resolution is recorded but not a security boundary; connectivity is",
                        "evidence": probe[1],
                    },
                    "public_http": {"allowed": bool(http), "evidence": probe[1]},
                    "deepseek_direct": {"allowed": bool(http or https), "evidence": probe[1]},
                    "gateway_internal": {"reachable": bool(gateway), "evidence": probe[1]},
                }
                if http or https:
                    errors.append("provider container reached the public DeepSeek endpoint")
                if not gateway:
                    errors.append("provider container could not reach the internal gateway")

        # Host-side inspection of the running provider container.
        inspect = run(["docker", "inspect", provider_id], timeout=60)
        if inspect is None or inspect[0] != 0:
            errors.append(f"docker inspect failed: {inspect}")
        else:
            info = json.loads(inspect[1])[0]
            host_config = info.get("HostConfig", {})
            mounts = info.get("Mounts", [])
            networks = info.get("NetworkSettings", {}).get("Networks", {})
            tmpfs_paths = sorted((host_config.get("Tmpfs") or {}).keys())
            rw_mounts = [mount for mount in mounts if mount.get("RW")]
            gold_mounts = [
                str(mount.get("Source") or mount.get("Name"))
                for mount in mounts
                if any(token in str(mount.get("Source", "")) for token in ("scorer_private", "ground_truth", "datasets"))
            ]
            inspection = {
                "provider_containers": 1,
                "container_id": provider_id,
                "read_only_root": bool(host_config.get("ReadonlyRootfs")),
                "no_new_privileges": any(
                    "no-new-privileges" in str(value) for value in (host_config.get("SecurityOpt") or [])
                ),
                "cap_drops": host_config.get("CapDrop") or [],
                "mem_limit": host_config.get("Memory"),
                "pids_limit": host_config.get("PidsLimit"),
                "nano_cpus": host_config.get("NanoCpus"),
                "user": info.get("Config", {}).get("User"),
                "tmpfs": tmpfs_paths,
                "networks": sorted(networks.keys()),
                "rw_mounts": [
                    {
                        "type": mount.get("Type"),
                        "name": mount.get("Name"),
                        "source": mount.get("Source"),
                        "target": mount.get("Destination"),
                    }
                    for mount in rw_mounts
                ],
                "gold_mounts": gold_mounts,
            }
            evidence["inspection"] = inspection
            if gold_mounts:
                errors.append(f"gold/private path mounted into provider: {gold_mounts}")
            if not inspection["read_only_root"]:
                errors.append("provider root is not read-only")
            if not inspection["no_new_privileges"]:
                errors.append("no-new-privileges is missing")
            if "ALL" not in (inspection["cap_drops"] or []):
                errors.append("cap_drop ALL is missing")
            if not inspection["mem_limit"] or not inspection["pids_limit"]:
                errors.append("resource limits are missing")
            if not inspection["user"] or inspection["user"] == "0":
                errors.append("provider must run as an explicit non-root user")
            observed_rw = {(mount.get("Destination"), mount.get("Type")) for mount in rw_mounts}
            observed_rw |= {(path, "tmpfs") for path in tmpfs_paths}
            allowed_rw = {("/provider-state", "volume")}
            if "/tmp" in tmpfs_paths:
                allowed_rw.add(("/tmp", "tmpfs"))
            if observed_rw != allowed_rw:
                errors.append(f"unexpected writable mounts: {sorted(observed_rw - allowed_rw)}")
            network_names = set(networks.keys())
            if not any(name.endswith("_bench-internal") or name == "bench-internal" for name in network_names):
                errors.append("provider is not attached to the internal network")
            if any(name.endswith("_bench-egress") or name == "bench-egress" for name in network_names):
                errors.append("provider is attached to the egress network")
    finally:
        teardown = run([*compose, "down", "-v", "--remove-orphans"], timeout=180, env=compose_env)
        if teardown is None or teardown[0] != 0:
            errors.append(f"probe stack teardown failed: {teardown}")

        def remaining(resource: str) -> list[str]:
            if resource == "ps":
                cmd = ["docker", "ps", "-a"]
            else:
                cmd = ["docker", resource, "ls"]
            cmd += [
                "--filter",
                "label=com.docker.compose.project=" + project,
                "--format",
                "{{.ID}}" if resource == "ps" else "{{.Name}}",
            ]
            result = run(cmd, timeout=30)
            if result is None or result[0] != 0:
                errors.append(
                    f"could not list remaining {resource}: "
                    f"{result[2] if result else 'no output'}"
                )
                return []
            return result[1].splitlines()

        containers = remaining("ps")
        networks_after = remaining("network")
        volumes_after = remaining("volume")
        evidence["cleanup"] = {
            "containers_remaining": len(containers),
            "networks_remaining": len(networks_after),
            "volumes_remaining": len(volumes_after),
        }
        if containers or networks_after or volumes_after:
            errors.append(
                f"run-scoped resources remain: containers={containers} networks={networks_after} volumes={volumes_after}"
            )

    evidence["passed"] = not errors
    _write_evidence(evidence, out_path)
    return evidence


def _write_evidence(evidence: dict, out_path: Path | None) -> None:
    if not out_path:
        return
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(evidence, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
