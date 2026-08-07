"""Static and rendered Compose policy checks for the clean-room contract.

Static checks operate on the Compose text files we control. Rendered checks
operate on ``docker compose config --format json`` output, which is the
authoritative expansion of the Compose model. Neither is a substitute for the
runtime probe in ``docker_probe.py``; policy evidence and runtime evidence are
recorded separately.
"""

from __future__ import annotations

import re

GOLD_TOKENS = ("scorer_private", "ground_truth")


def _service_blocks(compose_text: str) -> dict[str, list[str]]:
    """Very small service-block splitter for the compose files we control."""
    services: dict[str, list[str]] = {}
    current: str | None = None
    for line in compose_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not line.startswith("  ") and line.endswith(":"):
            current = None
            continue
        match = re.match(r"^  ([A-Za-z0-9_.-]+):", line)
        if match:
            current = match.group(1)
            services.setdefault(current, [])
            continue
        if current is not None:
            services[current].append(line)
    return services


def _volume_refs(block: list[str]) -> list[str]:
    refs = []
    for line in block:
        match = re.match(r"\s*-\s*([A-Za-z0-9_.-]+):", line)
        if match:
            refs.append(match.group(1))
    return refs


def check_static_policy(compose_text: str) -> list[str]:
    """Return a list of policy violations; an empty list means the policy passes."""
    issues: list[str] = []
    blocks = _service_blocks(compose_text)

    if re.search(r"^\s*network_mode:\s*host\s*$", compose_text, flags=re.MULTILINE):
        issues.append("host networking is forbidden")
    if re.search(r"^\s*privileged:\s*true\s*$", compose_text, flags=re.MULTILINE):
        issues.append("privileged mode is forbidden")
    non_comment_lines = [line for line in compose_text.splitlines() if not line.lstrip().startswith("#")]
    if not any("internal: true" in line for line in non_comment_lines):
        issues.append("an internal (egress-blocked) network must be declared")

    for token in GOLD_TOKENS:
        if any(token in line for line in compose_text.splitlines() if not line.lstrip().startswith("#")):
            issues.append(f"gold/private path token {token!r} must never appear in Compose")

    provider_services = [
        name for name, block in blocks.items() if any("/provider-state" in line for line in block)
    ]
    if len(provider_services) != 1:
        issues.append(f"expected exactly one provider service mounting /provider-state, found {provider_services}")
    elif provider_services:
        provider_block = blocks[provider_services[0]]
        if not any("read_only: true" in line for line in provider_block):
            issues.append("provider root filesystem must be read_only")
        if any("bench-egress" in line for line in provider_block):
            issues.append("provider must not be attached to the egress network (bench-egress)")

    egress_services = [name for name, block in blocks.items() if any("bench-egress" in line for line in block)]
    if egress_services and any(name != "gateway" for name in egress_services):
        issues.append(f"only the gateway may use the egress network, found: {sorted(egress_services)}")

    references: dict[str, list[str]] = {}
    for name, block in blocks.items():
        for ref in _volume_refs(block):
            references.setdefault(ref, []).append(name)
    for source, owners in sorted(references.items()):
        if len(owners) > 1:
            issues.append(f"volume {source!r} is shared between services: {sorted(owners)}")

    return issues


def check_rendered_policy(rendered: dict, *, probe: bool = False) -> list[str]:
    """Check the expanded Compose model (``docker compose config --format json``)."""
    issues: list[str] = []
    services = rendered.get("services") or {}
    networks = rendered.get("networks") or {}

    providers = [
        name
        for name, service in services.items()
        if any((volume or {}).get("target") == "/provider-state" for volume in (service.get("volumes") or []))
    ]
    if len(providers) != 1:
        issues.append(f"expected exactly one provider service mounting /provider-state, found {providers}")
        return issues

    provider = providers[0]
    service = services[provider]
    image = service.get("image") or ""
    tag = image.rsplit(":", 1)[1] if ":" in image else ""
    if not image or not tag or tag == "latest":
        issues.append(f"provider image must be pinned to a non-latest tag: {image!r}")
    if not service.get("read_only"):
        issues.append("provider root filesystem must be read_only")
    if "no-new-privileges:true" not in (service.get("security_opt") or []):
        issues.append("provider must set security_opt no-new-privileges")
    if "ALL" not in (service.get("cap_drop") or []):
        issues.append("provider must drop ALL capabilities")
    if not service.get("mem_limit") or not service.get("pids_limit") or service.get("cpus") is None:
        issues.append("provider must declare mem_limit, pids_limit, and cpus limits")
    if probe and not service.get("user"):
        issues.append("probe provider must run as an explicit non-root user")

    for network_name in service.get("networks") or {}:
        if not (networks.get(network_name) or {}).get("internal"):
            issues.append(f"provider network {network_name!r} is not internal")

    references: dict[str, list[str]] = {}
    for name, candidate in services.items():
        for volume in candidate.get("volumes") or []:
            source = (volume or {}).get("source")
            if source:
                references.setdefault(source, []).append(name)
    for source, owners in sorted(references.items()):
        if len(owners) > 1:
            issues.append(f"volume {source!r} is shared between services: {sorted(owners)}")

    return issues
