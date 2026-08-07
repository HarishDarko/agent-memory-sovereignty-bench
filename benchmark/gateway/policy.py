"""Gateway policy: upstream allowlist, request rules, budgets, and attestation."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)


class BudgetExceeded(RuntimeError):
    """Raised before dispatch when a global or per-run ceiling would be exceeded."""


@dataclass
class GatewayPolicy:
    allowed_upstream_hosts: list[str] = field(default_factory=lambda: ["api.deepseek.com"])
    allowed_upstream_paths: list[str] = field(default_factory=lambda: ["/chat/completions", "/v1/chat/completions"])
    allowed_model_aliases: list[str] = field(default_factory=lambda: ["deepseek-v4-flash"])
    expected_release: str = "DeepSeek-V4-Flash-0731"
    attestation_mode: str = "rolling"  # "rolling" labels; "strict" requires release evidence
    max_messages: int = 2
    max_retries: int = 2
    max_requests_per_run: int = 1000
    max_tokens_per_run: int = 2_000_000
    max_cost_usd_per_run: float = 1.0
    max_requests_global: int = 10_000
    max_tokens_global: int = 20_000_000
    max_cost_usd_global: float = 10.0
    price_per_million_input: float = 0.0
    price_per_million_output: float = 0.0
    enforce_budget: bool = True  # False: record usage only, never refuse (provider-side limits govern)

    @classmethod
    def load(cls, path: Path | str) -> "GatewayPolicy":
        import tomllib

        with open(path, "rb") as handle:
            data = tomllib.load(handle)
        upstream = data.get("upstream", {})
        models = data.get("models", {})
        limits = data.get("limits", {})
        pricing = data.get("pricing", {})
        return cls(
            allowed_upstream_hosts=list(upstream.get("allowed_hosts", ["api.deepseek.com"])),
            allowed_upstream_paths=list(upstream.get("allowed_paths", ["/chat/completions", "/v1/chat/completions"])),
            allowed_model_aliases=list(models.get("allowed_aliases", ["deepseek-v4-flash"])),
            expected_release=str(models.get("expected_release", "DeepSeek-V4-Flash-0731")),
            attestation_mode=str(models.get("attestation_mode", "rolling")),
            max_messages=int(limits.get("max_messages", 2)),
            max_retries=int(limits.get("max_retries", 2)),
            max_requests_per_run=int(limits.get("max_requests_per_run", 1000)),
            max_tokens_per_run=int(limits.get("max_tokens_per_run", 2_000_000)),
            max_cost_usd_per_run=float(limits.get("max_cost_usd_per_run", 1.0)),
            max_requests_global=int(limits.get("max_requests_global", 10_000)),
            max_tokens_global=int(limits.get("max_tokens_global", 20_000_000)),
            max_cost_usd_global=float(limits.get("max_cost_usd_global", 10.0)),
            price_per_million_input=float(pricing.get("price_per_million_input", 0.0)),
            price_per_million_output=float(pricing.get("price_per_million_output", 0.0)),
            enforce_budget=bool(limits.get("enforce_budget", True)),
        )

    def to_dict(self) -> dict:
        return {
            "allowed_upstream_hosts": self.allowed_upstream_hosts,
            "allowed_upstream_paths": self.allowed_upstream_paths,
            "allowed_model_aliases": self.allowed_model_aliases,
            "expected_release": self.expected_release,
            "attestation_mode": self.attestation_mode,
            "max_messages": self.max_messages,
            "max_retries": self.max_retries,
            "max_requests_per_run": self.max_requests_per_run,
            "max_tokens_per_run": self.max_tokens_per_run,
            "max_cost_usd_per_run": self.max_cost_usd_per_run,
            "max_requests_global": self.max_requests_global,
            "max_tokens_global": self.max_tokens_global,
            "max_cost_usd_global": self.max_cost_usd_global,
            "price_per_million_input": self.price_per_million_input,
            "price_per_million_output": self.price_per_million_output,
        }


def check_upstream_target(policy: GatewayPolicy, url: str) -> list[str]:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    loopback = host in LOOPBACK_HOSTS
    issues: list[str] = []
    if parsed.scheme != "https" and not loopback:
        issues.append(f"upstream scheme must be https, got {parsed.scheme!r}")
    if not loopback and host not in policy.allowed_upstream_hosts:
        issues.append(f"upstream host {host!r} not allowlisted")
    if parsed.path not in policy.allowed_upstream_paths:
        issues.append(f"upstream path {parsed.path!r} not allowlisted")
    return issues


def check_request(policy: GatewayPolicy, request: dict, identity: dict) -> list[str]:
    issues: list[str] = []
    if not identity.get("run_id"):
        issues.append("missing run_id identity")
    if not identity.get("provider_id"):
        issues.append("missing provider_id identity")
    messages = request.get("messages")
    if not isinstance(messages, list) or not messages:
        issues.append("request must contain a non-empty messages list")
    elif len(messages) > policy.max_messages:
        issues.append(
            f"conversation history reuse: {len(messages)} messages exceed max {policy.max_messages}"
        )
    model = request.get("model")
    if model not in policy.allowed_model_aliases:
        issues.append(f"model {model!r} not in allowlist {policy.allowed_model_aliases}")
    return issues


@dataclass
class BudgetState:
    run_requests: dict = field(default_factory=dict)
    run_tokens_in: dict = field(default_factory=dict)
    run_tokens_out: dict = field(default_factory=dict)
    run_cost: dict = field(default_factory=dict)
    global_requests: int = 0
    global_tokens: int = 0
    global_cost: float = 0.0
    lock: threading.Lock = field(default_factory=threading.Lock)

    def check_and_charge(self, policy: GatewayPolicy, run_id: str, input_tokens: int, output_tokens: int) -> None:
        with self.lock:
            cost = (
                input_tokens * policy.price_per_million_input
                + output_tokens * policy.price_per_million_output
            ) / 1_000_000
            run_req = self.run_requests.get(run_id, 0)
            run_tokens = self.run_tokens_in.get(run_id, 0) + self.run_tokens_out.get(run_id, 0)
            run_cost = self.run_cost.get(run_id, 0.0)
            if policy.enforce_budget:
                if run_req + 1 > policy.max_requests_per_run:
                    raise BudgetExceeded("per-run request ceiling exceeded")
                if run_tokens + input_tokens + output_tokens > policy.max_tokens_per_run:
                    raise BudgetExceeded("per-run token ceiling exceeded")
                if run_cost + cost > policy.max_cost_usd_per_run:
                    raise BudgetExceeded("per-run cost ceiling exceeded")
                if self.global_requests + 1 > policy.max_requests_global:
                    raise BudgetExceeded("global request ceiling exceeded")
                if self.global_tokens + input_tokens + output_tokens > policy.max_tokens_global:
                    raise BudgetExceeded("global token ceiling exceeded")
                if self.global_cost + cost > policy.max_cost_usd_global:
                    raise BudgetExceeded("global cost ceiling exceeded")
            self.run_requests[run_id] = run_req + 1
            self.run_tokens_in[run_id] = self.run_tokens_in.get(run_id, 0) + input_tokens
            self.run_tokens_out[run_id] = self.run_tokens_out.get(run_id, 0) + output_tokens
            self.run_cost[run_id] = run_cost + cost
            self.global_requests += 1
            self.global_tokens += input_tokens + output_tokens
            self.global_cost += cost


def check_response(policy: GatewayPolicy, payload: dict) -> list[str]:
    issues: list[str] = []
    if not isinstance(payload, dict):
        return ["response is not a JSON object"]
    if not payload.get("id"):
        issues.append("response missing id")
    if not payload.get("model"):
        issues.append("response missing model")
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        issues.append("response missing choices")
    usage = payload.get("usage")
    if (
        not isinstance(usage, dict)
        or usage.get("prompt_tokens") is None
        or usage.get("completion_tokens") is None
    ):
        issues.append("response missing usage prompt_tokens/completion_tokens")
    return issues


def attest_model(requested: str, returned: str | None, expected_release: str, mode: str) -> dict:
    returned_norm = (returned or "").strip().lower()
    expected_norm = (expected_release or "").strip().lower().replace(" ", "-").replace("_", "-")
    if mode == "strict":
        ok = bool(returned_norm) and expected_norm in returned_norm
        label = (
            "attested to expected release"
            if ok
            else f"returned model {returned!r} does not evidence expected release {expected_release!r}"
        )
    else:
        ok = True
        label = (
            f"rolling alias {requested!r} observed; returned model {returned!r}; "
            "dated checkpoint not asserted"
        )
    return {
        "ok": ok,
        "label": label,
        "mode": mode,
        "requested_model": requested,
        "returned_model": returned,
        "expected_release": expected_release,
    }
