"""Local OpenAI-compatible gateway proxy.

Accepts chat completion requests with benchmark identity headers, enforces the
policy (upstream allowlist, single-turn request shape, model allowlist, budget
ceilings), forwards only to the official DeepSeek endpoint, attests the
returned model, and records every attempt in a hash-chained ledger.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from benchmark.gateway.ledger import Ledger
from benchmark.gateway.policy import (
    BudgetExceeded,
    BudgetState,
    GatewayPolicy,
    attest_model,
    check_request,
    check_response,
    check_upstream_target,
    estimate_tokens,
)

ALLOWED_PATHS = ("/chat/completions", "/v1/chat/completions")


def _sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class GatewayProxyHandler(BaseHTTPRequestHandler):
    server_version = "SovbenchGateway/0.1"

    def do_POST(self) -> None:
        self._started = time.perf_counter()
        entry = {
            "ts": _now_utc(),
            "run_id": "",
            "provider_id": "",
            "requested_model": None,
            "returned_model": None,
            "request_id": None,
            "retries": 0,
            "usage": None,
            "estimated_usage": {"input_tokens": 0, "output_tokens": 0},
            "status": 200,
            "error_class": None,
            "attestation": None,
            "request_hash": "",
            "response_hash": "",
        }
        try:
            if self.path not in ALLOWED_PATHS:
                entry.update({"status": 404, "error_class": "unsupported_path"})
                self._send(404, {"error": {"class": "unsupported_path", "message": f"unsupported path {self.path!r}"}}, entry)
                return

            length = int(self.headers.get("Content-Length", 0) or 0)
            raw_request = self.rfile.read(length) if length else b"{}"
            entry["request_hash"] = _sha256_bytes(raw_request)
            request = json.loads(raw_request or b"{}")
            entry["requested_model"] = request.get("model")
            entry["run_id"] = self.headers.get("X-Sovbench-Run-Id") or ""
            entry["provider_id"] = self.headers.get("X-Sovbench-Provider-Id") or ""
            if not entry["run_id"] and not self.server.require_identity:
                stamped = self.server.stamp_identity or {}
                entry["run_id"] = stamped.get("run_id", "")
                entry["provider_id"] = stamped.get("provider_id", "")
            identity = {"run_id": entry["run_id"], "provider_id": entry["provider_id"]}

            issues = (
                [] if not self.server.require_identity else check_request(self.server.policy, request, identity)
            )
            if issues:
                if any("run_id" in issue or "provider_id" in issue for issue in issues):
                    error_class = "missing_identity"
                elif any("history" in issue.lower() for issue in issues):
                    error_class = "history_reuse"
                else:
                    error_class = "model_not_allowed"
                entry.update({"status": 403, "error_class": error_class})
                self._send(403, {"error": {"class": error_class, "message": "; ".join(issues)}}, entry)
                return

            estimated_input = sum(
                estimate_tokens(str(message.get("content", ""))) for message in request.get("messages", [])
            )
            estimated_output = int(request.get("max_tokens") or 0)
            entry["estimated_usage"] = {"input_tokens": estimated_input, "output_tokens": estimated_output}
            try:
                self.server.budget.check_and_charge(
                    self.server.policy, entry["run_id"], estimated_input, estimated_output
                )
            except BudgetExceeded as exc:
                entry.update({"status": 429, "error_class": "budget_exceeded"})
                self._send(429, {"error": {"class": "budget_exceeded", "message": str(exc)}}, entry)
                return

            payload, status, retries, raw_response = self._forward(request)
            entry.update(
                {
                    "status": status,
                    "retries": retries,
                    "response_hash": _sha256_bytes(raw_response or b""),
                }
            )
            if status != 200:
                entry["error_class"] = "upstream_error"
                self._send(
                    status,
                    {"error": {"class": "upstream_error", "message": str(payload.get("error", payload))[:500]}},
                    entry,
                )
                return

            issues = check_response(self.server.policy, payload)
            if issues:
                entry.update({"status": 502, "error_class": "invalid_response"})
                self._send(502, {"error": {"class": "invalid_response", "message": "; ".join(issues)}}, entry)
                return

            entry["returned_model"] = payload.get("model")
            entry["request_id"] = payload.get("id")
            entry["usage"] = payload.get("usage")
            attestation = attest_model(
                entry["requested_model"] or "",
                entry["returned_model"],
                self.server.policy.expected_release,
                self.server.policy.attestation_mode,
            )
            entry["attestation"] = attestation["label"]
            if not attestation["ok"]:
                entry.update({"status": 502, "error_class": "attestation_failed"})
                self._send(502, {"error": {"class": "attestation_failed", "message": attestation["label"]}}, entry)
                return

            self._send(200, payload, entry)
        except json.JSONDecodeError as exc:
            entry.update({"status": 400, "error_class": "invalid_request_json"})
            self._send(400, {"error": {"class": "invalid_request_json", "message": str(exc)}}, entry)
        except Exception as exc:  # noqa: BLE001 - the ledger must always record
            entry.update(
                {
                    "status": 500,
                    "error_class": entry.get("error_class") or "internal_error",
                }
            )
            self._send(
                500,
                {"error": {"class": entry["error_class"], "message": str(exc)[:500]}},
                entry,
            )

    def _send(self, status: int, body: dict, entry: dict) -> None:
        """Append the ledger entry BEFORE the response so an observed response
        always has a durable record."""
        entry["latency_ms"] = round((time.perf_counter() - self._started) * 1000.0, 3)
        self.server.ledger.append(entry)
        data = json.dumps(body, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _forward(self, request: dict):
        body = json.dumps(request, separators=(",", ":")).encode("utf-8")
        upstream_request = urllib.request.Request(
            self.server.upstream_url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.server.api_key}",
            },
        )
        retries = 0
        while True:
            try:
                with urllib.request.urlopen(upstream_request, timeout=self.server.timeout_s) as response:
                    raw = response.read()
                    return json.loads(raw), response.status, retries, raw
            except urllib.error.HTTPError as exc:
                raw = exc.read()
                if exc.code in (429, 500, 502, 503, 504) and retries < self.server.policy.max_retries:
                    retries += 1
                    time.sleep(1.0 * retries)
                    continue
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError:
                    payload = {"error": {"class": "upstream_error", "message": exc.reason}}
                return payload, exc.code, retries, raw
            except (urllib.error.URLError, OSError) as exc:
                if retries < self.server.policy.max_retries:
                    retries += 1
                    time.sleep(0.5 * retries)
                    continue
                return {"error": {"class": "upstream_unreachable", "message": str(exc)}}, 502, retries, None

    def log_message(self, format, *args):  # noqa: A002 - keep stdout clean for orchestration
        pass


def create_server(
    policy: GatewayPolicy,
    ledger: Ledger,
    upstream_url: str,
    api_key: str,
    port: int = 0,
    timeout_s: float = 60.0,
    bind_host: str = "127.0.0.1",
    require_identity: bool = True,
    stamp_identity: dict | None = None,
) -> ThreadingHTTPServer:
    issues = check_upstream_target(policy, upstream_url)
    if issues:
        raise ValueError("upstream rejected by gateway policy: " + "; ".join(issues))
    server = ThreadingHTTPServer((bind_host, port), GatewayProxyHandler)
    server.policy = policy
    server.ledger = ledger
    server.upstream_url = upstream_url
    server.api_key = api_key
    server.timeout_s = timeout_s
    server.require_identity = require_identity
    server.stamp_identity = stamp_identity
    server.budget = BudgetState()
    return server


def main() -> None:
    repo = Path(__file__).resolve().parent.parent.parent
    policy_path = Path(os.environ.get("GATEWAY_POLICY_PATH", repo / "config" / "gateway-policy.toml"))
    ledger_path = Path(os.environ.get("GATEWAY_LEDGER_PATH", "/tmp/gateway-ledger.jsonl"))
    base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    port = int(os.environ.get("GATEWAY_PORT", "8000"))
    policy = GatewayPolicy.load(policy_path) if policy_path.exists() else GatewayPolicy()
    server = create_server(
        policy=policy,
        ledger=Ledger(ledger_path),
        upstream_url=base_url + "/chat/completions",
        api_key=api_key,
        port=port,
    )
    print(f"gateway listening on 127.0.0.1:{server.server_port} -> {server.upstream_url}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    sys.exit(main())
