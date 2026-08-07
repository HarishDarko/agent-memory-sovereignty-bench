import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest.mock import patch

from benchmark.config import load_settings
from benchmark.events import Query
from benchmark.model_gateway import (
    DeepSeekGateway,
    GatewayError,
    GatewayNotConfigured,
    GatewayRateLimit,
    OfflineGateway,
    _parse_structured,
    get_gateway,
)
from benchmark.providers import RetrievedItem


def _settings(tmp):
    s = load_settings()
    s.prompt_path = Path(tmp) / "prompts" / "reader-v1.md"
    (s.prompt_path).parent.mkdir(parents=True, exist_ok=True)
    s.prompt_path.write_text("Reader prompt for tests.", encoding="utf-8")
    return s


class TestOfflineGateway(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.settings = _settings(self.tmp.name)
        self.q = Query("q1", "What is Maren Vale's preferred editor?", "person_01", "personal", "2026-08-01T00:00:00Z")

    def tearDown(self):
        self.tmp.cleanup()

    def test_no_evidence_abstains(self):
        gateway = OfflineGateway(self.settings)
        resp = gateway.generate(self.q, [], "v1")
        self.assertTrue(resp.structured["abstain"])
        self.assertIsNone(resp.structured["answer"])
        self.assertEqual(len(resp.prompt_hash), 64)

    def test_evidence_copies_top_item(self):
        gateway = OfflineGateway(self.settings)
        items = [RetrievedItem("event_0001", "Maren Vale's preferred editor is Quill.")]
        resp = gateway.generate(self.q, items, "v1")
        self.assertFalse(resp.structured["abstain"])
        self.assertEqual(resp.structured["answer"], "Maren Vale's preferred editor is Quill.")
        self.assertEqual(resp.structured["evidence_ids"], ["event_0001"])

    def test_accounting_fields(self):
        gateway = OfflineGateway(self.settings)
        resp = gateway.generate(self.q, [], "v1")
        self.assertEqual(resp.mode, "offline")
        self.assertGreaterEqual(resp.request_tokens, 0)
        self.assertGreaterEqual(resp.response_tokens, 0)
        self.assertEqual(resp.retries, 0)

    def test_log_written(self):
        log = Path(self.tmp.name) / "gateway.log"
        gateway = OfflineGateway(self.settings, log_path=log)
        gateway.generate(self.q, [], "v1")
        lines = log.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), 1)
        self.assertEqual(json.loads(lines[0])["gateway_mode"], "offline")

    def test_prompt_hash_stable(self):
        a = OfflineGateway(self.settings)
        b = OfflineGateway(self.settings)
        self.assertEqual(a.generate(self.q, [], "v1").prompt_hash, b.generate(self.q, [], "v1").prompt_hash)


class TestDeepSeekGateway(unittest.TestCase):
    def test_structured_reader_output_is_strictly_validated(self):
        invalid = [
            '{"answer": null, "confidence": 1, "abstain": "false", "evidence_ids": []}',
            '{"answer": null, "confidence": 2, "abstain": true, "evidence_ids": []}',
            '{"answer": "guess", "confidence": 1, "abstain": true, "evidence_ids": []}',
            '{"answer": "x", "confidence": 1, "abstain": false, "evidence_ids": "ev1"}',
            '{"answer": "x", "confidence": 1, "abstain": false, "evidence_ids": [], "extra": 1}',
        ]
        for payload in invalid:
            with self.subTest(payload=payload), self.assertRaises(GatewayError):
                _parse_structured(payload)

    def test_identity_headers_sent_when_routed_through_proxy(self):
        captured = {}

        class CaptureHandler(BaseHTTPRequestHandler):
            def do_POST(self):
                captured["headers"] = dict(self.headers)
                length = int(self.headers.get("Content-Length", 0))
                self.rfile.read(length)
                body = json.dumps(
                    {
                        "id": "req-1",
                        "model": "deepseek-v4-flash-0731",
                        "choices": [
                            {"message": {"content": '{"answer": null, "confidence": 1, "abstain": true, "evidence_ids": []}'}}
                        ],
                        "usage": {"prompt_tokens": 1, "completion_tokens": 1},
                    }
                ).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        server = HTTPServer(("127.0.0.1", 0), CaptureHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        tmp = tempfile.TemporaryDirectory()
        try:
            settings = _settings(tmp.name)
            settings.gateway_mode = "deepseek"
            settings.api_key = "sk-test"
            settings.gateway_url = f"http://127.0.0.1:{server.server_port}"
            settings.identity_run_id = "run-9"
            settings.identity_provider_id = "provider-9"
            gateway = DeepSeekGateway(settings)
            gateway.generate(Query("q1", "question?", "user_001", "personal", "2026-08-01T00:00:00Z"), [], "v1")
            self.assertEqual(captured["headers"].get("X-Sovbench-Run-Id"), "run-9")
            self.assertEqual(captured["headers"].get("X-Sovbench-Provider-Id"), "provider-9")
            self.assertTrue(captured["headers"].get("Authorization").startswith("Bearer "))
        finally:
            server.shutdown()
            server.server_close()
            tmp.cleanup()

    def test_requires_api_key(self):
        tmp = tempfile.TemporaryDirectory()
        settings = _settings(tmp.name)
        settings.gateway_mode = "deepseek"
        settings.api_key = ""
        gateway = DeepSeekGateway(settings)
        with self.assertRaises(GatewayNotConfigured):
            gateway.generate(
                Query("q1", "question?", "person_01", "personal", "2026-08-01T00:00:00Z"),
                [],
                "v1",
            )
        tmp.cleanup()

    def test_factory(self):
        tmp = tempfile.TemporaryDirectory()
        settings = _settings(tmp.name)
        settings.gateway_mode = "offline"
        self.assertIsInstance(get_gateway(settings), OfflineGateway)
        settings.gateway_mode = "bogus"
        with self.assertRaises(GatewayError):
            get_gateway(settings)
        tmp.cleanup()

    def test_retry_count_and_response_identity_are_preserved(self):
        tmp = tempfile.TemporaryDirectory()
        settings = _settings(tmp.name)
        settings.gateway_mode = "deepseek"
        settings.api_key = "test-only"
        gateway = DeepSeekGateway(settings)
        calls = [
            GatewayRateLimit("retry"),
            {
                "id": "request-123",
                "model": "deepseek-v4-flash-0731",
                "choices": [{"message": {"content": '{"answer": null, "confidence": 1, "abstain": true, "evidence_ids": []}'}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 3},
            },
        ]

        def fake_post(_body):
            result = calls.pop(0)
            if isinstance(result, Exception):
                raise result
            return result

        gateway._post = fake_post
        with patch("benchmark.model_gateway.time.sleep"):
            response = gateway.generate(
                Query("q1", "question?", "user_001", "personal", "2026-08-01T00:00:00Z"), [], "v1"
            )

        self.assertEqual(response.retries, 1)
        self.assertEqual(response.response_model_id, "deepseek-v4-flash-0731")
        self.assertEqual(response.request_id, "request-123")
        self.assertEqual(response.request_tokens, 10)
        self.assertEqual(response.response_tokens, 3)
        tmp.cleanup()

    def test_empty_content_is_retried_bounded_then_succeeds(self):
        tmp = tempfile.TemporaryDirectory()
        settings = _settings(tmp.name)
        settings.gateway_mode = "deepseek"
        settings.api_key = "test-only"
        settings.max_retries = 2
        gateway = DeepSeekGateway(settings)
        calls = {"n": 0}

        def payload(content):
            calls["n"] += 1
            return {
                "id": f"request-{calls['n']}",
                "model": "deepseek-v4-flash",
                "choices": [{"message": {"content": content}}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 2},
            }

        responses = [
            payload(""),
            payload(""),
            payload('{"answer": null, "confidence": 1, "abstain": true, "evidence_ids": []}'),
        ]
        gateway._post = lambda _body: responses.pop(0)
        with patch("benchmark.model_gateway.time.sleep"):
            response = gateway.generate(
                Query("q1", "question?", "user_001", "personal", "2026-08-01T00:00:00Z"), [], "v1"
            )
        self.assertTrue(response.structured["abstain"])
        self.assertEqual(calls["n"], 3)
        self.assertEqual(response.retries, 2)
        tmp.cleanup()

    def test_persistent_empty_content_fails_honestly(self):
        tmp = tempfile.TemporaryDirectory()
        settings = _settings(tmp.name)
        settings.gateway_mode = "deepseek"
        settings.api_key = "test-only"
        settings.max_retries = 1
        gateway = DeepSeekGateway(settings)
        gateway._post = lambda _body: {
            "id": "request-x",
            "model": "deepseek-v4-flash",
            "choices": [{"message": {"content": ""}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 2},
        }
        with patch("benchmark.model_gateway.time.sleep"):
            with self.assertRaises(GatewayError):
                gateway.generate(
                    Query("q1", "question?", "user_001", "personal", "2026-08-01T00:00:00Z"), [], "v1"
                )
        tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
