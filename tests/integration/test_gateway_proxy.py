"""End-to-end proxy test against a fake upstream on localhost. No Docker, no real API."""

import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from benchmark.gateway.ledger import Ledger
from benchmark.gateway.policy import GatewayPolicy
from benchmark.gateway.server import create_server


class FakeUpstreamHandler(BaseHTTPRequestHandler):
    received_headers = {}

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        self.server.last_body = self.rfile.read(length)
        FakeUpstreamHandler.received_headers = dict(self.headers)
        if self.server.mode == "missing_model":
            payload = {"id": "upstream-1", "choices": [{"message": {"content": "{}"}}]}
        elif self.server.mode == "wrong_model":
            payload = {
                "id": "upstream-1",
                "model": "deepseek-v4-flash-preview",
                "choices": [{"message": {"content": "{}"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            }
        else:
            payload = {
                "id": "upstream-1",
                "model": "deepseek-v4-flash-0731",
                "choices": [{"message": {"content": '{"answer": "ok", "abstain": false, "evidence_ids": []}'}}],
                "usage": {"prompt_tokens": 11, "completion_tokens": 4},
            }
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def _policy(**overrides) -> GatewayPolicy:
    values = dict(
        allowed_upstream_hosts=["localhost", "api.deepseek.com"],
        allowed_upstream_paths=["/chat/completions", "/v1/chat/completions"],
        allowed_model_aliases=["deepseek-v4-flash"],
        max_messages=2,
        max_requests_per_run=100,
        max_tokens_per_run=1_000_000,
        max_cost_usd_per_run=1.0,
        max_requests_global=1000,
        max_tokens_global=10_000_000,
        max_cost_usd_global=10.0,
        attestation_mode="rolling",
        expected_release="DeepSeek-V4-Flash-0731",
    )
    values.update(overrides)
    return GatewayPolicy(**values)


class TestGatewayProxy(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ledger_path = Path(self.tmp.name) / "ledger.jsonl"
        self.ledger = Ledger(self.ledger_path)
        self.fake = HTTPServer(("127.0.0.1", 0), FakeUpstreamHandler)
        self.fake.mode = "ok"
        self.fake.last_body = None
        self.fake_thread = threading.Thread(target=self.fake.serve_forever, daemon=True)
        self.fake_thread.start()
        self.upstream_url = f"http://127.0.0.1:{self.fake.server_port}/chat/completions"
        self.proxy = create_server(
            policy=_policy(),
            ledger=self.ledger,
            upstream_url=self.upstream_url,
            api_key="sk-test-never-committed",
            port=0,
        )
        self.proxy_thread = threading.Thread(target=self.proxy.serve_forever, daemon=True)
        self.proxy_thread.start()
        self.proxy_url = f"http://127.0.0.1:{self.proxy.server_port}"

    def _anonymous_post(self, url: str) -> tuple[int, dict]:
        body = json.dumps(
            {
                "model": "deepseek-v4-flash",
                "messages": [
                    {"role": "system", "content": "s"},
                    {"role": "user", "content": "u"},
                ],
                "max_tokens": 10,
            }
        ).encode()
        request = urllib.request.Request(url + "/chat/completions", data=body, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read())

    def test_identity_stamping_accepts_anonymous_native_calls(self):
        ledger = Ledger(Path(self.tmp.name) / "ledger-native.jsonl")
        proxy = create_server(
            policy=_policy(),
            ledger=ledger,
            upstream_url=self.upstream_url,
            api_key="sk-test",
            port=0,
            require_identity=False,
            stamp_identity={"run_id": "mem0-native", "provider_id": "mem0"},
        )
        thread = threading.Thread(target=proxy.serve_forever, daemon=True)
        thread.start()
        try:
            status, _payload = self._anonymous_post(f"http://127.0.0.1:{proxy.server_port}")
            self.assertEqual(status, 200)
            entry = json.loads(ledger.path.read_text(encoding="utf-8").splitlines()[-1])
            self.assertEqual(entry["run_id"], "mem0-native")
            self.assertEqual(entry["provider_id"], "mem0")
            self.assertEqual(entry["requested_model"], "deepseek-v4-flash")
        finally:
            proxy.shutdown()
            proxy.server_close()

    def test_identity_required_refuses_anonymous_calls(self):
        status, payload = self._anonymous_post(self.proxy_url)
        self.assertEqual(status, 403)
        self.assertEqual(payload["error"]["class"], "missing_identity")

    def tearDown(self):
        self.proxy.shutdown()
        self.proxy.server_close()
        self.fake.shutdown()
        self.fake.server_close()
        self.tmp.cleanup()

    def _post(self, path="/chat/completions", body=None, headers=None):
        request = urllib.request.Request(
            self.proxy_url + path,
            data=json.dumps(body or self._request()).encode(),
            headers={
                "Content-Type": "application/json",
                "X-Sovbench-Run-Id": "run-1",
                "X-Sovbench-Provider-Id": "provider-1",
                **(headers or {}),
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return response.status, json.loads(response.read().decode())
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode())

    def _request(self, model="deepseek-v4-flash", messages=None):
        return {
            "model": model,
            "messages": messages
            or [
                {"role": "system", "content": "reader prompt"},
                {"role": "user", "content": "question + evidence"},
            ],
            "temperature": 0.0,
            "stream": False,
        }

    def _entries(self):
        return [json.loads(line) for line in self.ledger_path.read_text(encoding="utf-8").strip().splitlines()]

    def test_valid_request_forwards_and_ledgers(self):
        status, payload = self._post()
        self.assertEqual(status, 200)
        self.assertEqual(payload["model"], "deepseek-v4-flash-0731")
        self.assertEqual(FakeUpstreamHandler.received_headers.get("Authorization"), "Bearer sk-test-never-committed")
        entries = self._entries()
        self.assertEqual(len(entries), 1)
        entry = entries[0]
        self.assertEqual(entry["run_id"], "run-1")
        self.assertEqual(entry["provider_id"], "provider-1")
        self.assertEqual(entry["requested_model"], "deepseek-v4-flash")
        self.assertEqual(entry["returned_model"], "deepseek-v4-flash-0731")
        self.assertEqual(entry["request_id"], "upstream-1")
        self.assertEqual(entry["retries"], 0)
        self.assertEqual(entry["usage"]["prompt_tokens"], 11)
        self.assertEqual(entry["usage"]["completion_tokens"], 4)
        self.assertEqual(entry["error_class"], None)
        self.assertTrue(entry["request_hash"].startswith("sha256:"))
        self.assertTrue(entry["response_hash"].startswith("sha256:"))
        self.assertIn("latency_ms", entry)
        self.assertIn("estimated_usage", entry)
        self.assertEqual(self.ledger.verify(), [])

    def test_missing_identity_rejected_without_upstream_call(self):
        status, payload = self._post(headers={"X-Sovbench-Run-Id": "", "X-Sovbench-Provider-Id": ""})
        self.assertEqual(status, 403)
        self.assertEqual(payload["error"]["class"], "missing_identity")
        self.assertIsNone(self.fake.last_body)

    def test_history_reuse_rejected(self):
        messages = [
            {"role": "system", "content": "p"},
            {"role": "user", "content": "q1"},
            {"role": "assistant", "content": "a1"},
            {"role": "user", "content": "q2"},
        ]
        status, payload = self._post(body=self._request(messages=messages))
        self.assertEqual(status, 403)
        self.assertEqual(payload["error"]["class"], "history_reuse")
        self.assertIsNone(self.fake.last_body)

    def test_unknown_model_rejected(self):
        status, payload = self._post(body=self._request(model="gpt-4o"))
        self.assertEqual(status, 403)
        self.assertEqual(payload["error"]["class"], "model_not_allowed")

    def test_budget_ceiling_fails_closed(self):
        self.proxy.shutdown()
        self.proxy.server_close()
        self.proxy = create_server(
            policy=_policy(max_requests_per_run=1),
            ledger=self.ledger,
            upstream_url=self.upstream_url,
            api_key="sk-test",
            port=0,
        )
        self.proxy_thread = threading.Thread(target=self.proxy.serve_forever, daemon=True)
        self.proxy_thread.start()
        self.proxy_url = f"http://127.0.0.1:{self.proxy.server_port}"
        first = self._post()
        second = self._post()
        self.assertEqual(first[0], 200)
        self.assertEqual(second[0], 429)
        self.assertEqual(second[1]["error"]["class"], "budget_exceeded")

    def test_upstream_response_without_model_identity_fails_closed(self):
        self.fake.mode = "missing_model"
        status, payload = self._post()
        self.assertEqual(status, 502)
        self.assertEqual(payload["error"]["class"], "invalid_response")

    def test_strict_attestation_mismatch_fails_closed(self):
        self.fake.mode = "wrong_model"
        self.proxy.shutdown()
        self.proxy.server_close()
        self.proxy = create_server(
            policy=_policy(attestation_mode="strict"),
            ledger=self.ledger,
            upstream_url=self.upstream_url,
            api_key="sk-test",
            port=0,
        )
        self.proxy_thread = threading.Thread(target=self.proxy.serve_forever, daemon=True)
        self.proxy_thread.start()
        self.proxy_url = f"http://127.0.0.1:{self.proxy.server_port}"
        status, payload = self._post()
        self.assertEqual(status, 502)
        self.assertEqual(payload["error"]["class"], "attestation_failed")


if __name__ == "__main__":
    unittest.main()
