"""Model gateway: controlled route to DeepSeek V4 Flash.

Phase 0 runs in `offline` mode: a deterministic stub, effectively $0 and with
no network access. `deepseek` mode talks to the official DeepSeek API
(OpenAI-compatible) and is only active when explicitly enabled with a key.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from benchmark import hashing
from benchmark.clock import BenchmarkClock
from benchmark.config import Settings
from benchmark.events import Query
from benchmark.providers import RetrievedItem
from benchmark.token_budget import estimate_tokens, format_evidence
from benchmark.gateway.policy import attest_model


class GatewayError(RuntimeError):
    pass


class GatewayNotConfigured(GatewayError):
    pass


class GatewayRateLimit(GatewayError):
    pass


@dataclass
class ModelResponse:
    structured: dict
    model_id: str
    mode: str
    prompt_hash: str
    request_tokens: int
    response_tokens: int
    retries: int = 0
    latency_ms: float = 0.0
    response_model_id: Optional[str] = None
    request_id: Optional[str] = None
    raw: dict = field(default_factory=dict)
    usage: Optional[dict] = None
    attestation: Optional[dict] = None


class BaseGateway:
    mode = "base"

    def __init__(self, settings: Settings, clock: Optional[BenchmarkClock] = None, log_path: Optional[Path] = None):
        self.settings = settings
        self.clock = clock
        self.log_path = log_path

    def _now(self) -> str:
        if self.clock:
            return self.clock.now()
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _prompt_hash(self, version: str) -> str:
        if not self.settings.prompt_path.exists():
            raise GatewayError(f"reader prompt file missing: {self.settings.prompt_path}")
        return hashing.sha256_text(hashing.sha256_file(self.settings.prompt_path) + "|" + version)

    def _system_prompt(self) -> str:
        return self.settings.prompt_path.read_text(encoding="utf-8")

    def _log(self, record: dict) -> None:
        if not self.log_path:
            return
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, sort_keys=True, default=str) + "\n")

    def generate(self, query: Query, evidence: list[RetrievedItem], prompt_version: str) -> ModelResponse:
        raise NotImplementedError

    def describe(self) -> dict:
        return {
            "provider": "unknown",
            "requested_model": None,
            "actual_model": None,
            "semantic_reader_validated": False,
        }


class OfflineGateway(BaseGateway):
    """Deterministic plumbing stub.

    Semantics: empty evidence -> abstain (UNKNOWN); non-empty evidence -> copy
    the top item's text into the answer field. This is NOT a semantic reader;
    it exists so the full pipeline (normalization, budgeting, structured output,
    scoring, manifests) is verifiable with $0 and no network. Reader answer
    quality is only meaningful when mode=deepseek.
    """

    mode = "offline"

    def describe(self) -> dict:
        return {
            "provider": "local",
            "requested_model": None,
            "expected_release": self.settings.model_release,
            "actual_model": "stub-offline",
            "semantic_reader_validated": False,
        }

    def attest(self, requested_model: str, returned_model: Optional[str]) -> dict:
        return {"ok": True, "label": "offline stub; no model call", "mode": "offline"}

    def generate(self, query: Query, evidence: list[RetrievedItem], prompt_version: str) -> ModelResponse:
        t0 = time.perf_counter()
        prompt_hash = self._prompt_hash(prompt_version)
        if not evidence:
            structured = {"answer": None, "confidence": 1.0, "abstain": True, "evidence_ids": []}
        else:
            structured = {
                "answer": evidence[0].text,
                "confidence": 1.0,
                "abstain": False,
                "evidence_ids": [evidence[0].item_id],
            }
        bundle = format_evidence(evidence, budget=self.settings.token_budget)
        resp = ModelResponse(
            structured=structured,
            model_id="stub-offline",
            mode=self.mode,
            prompt_hash=prompt_hash,
            request_tokens=estimate_tokens(query.question) + estimate_tokens(bundle.text),
            response_tokens=estimate_tokens(json.dumps(structured, sort_keys=True)),
            retries=0,
            latency_ms=(time.perf_counter() - t0) * 1000.0,
            raw={"stub": True, "question": query.question},
        )
        self._log(
            {
                "ts": self._now(),
                "gateway_mode": self.mode,
                "query_id": query.query_id,
                "prompt_hash": prompt_hash,
                "request_tokens": resp.request_tokens,
                "response_tokens": resp.response_tokens,
                "retries": 0,
                "latency_ms": round(resp.latency_ms, 3),
                "structured": structured,
            }
        )
        return resp


class DeepSeekGateway(BaseGateway):
    """Official DeepSeek API (OpenAI-compatible), stateless per request."""

    mode = "deepseek"

    def describe(self) -> dict:
        return {
            "provider": "DeepSeek API",
            "requested_model": self.settings.model,
            "expected_release": self.settings.model_release,
            "actual_model": None,
            "semantic_reader_validated": True,
            "base_url": self.settings.base_url,
            "thinking_enabled": self.settings.thinking_enabled,
            "reasoning_effort": self.settings.reasoning_effort,
            "temperature": self.settings.temperature,
            "attestation_mode": self.settings.attestation_mode,
            "via_gateway_proxy": bool(self.settings.gateway_url),
        }

    def generate(self, query: Query, evidence: list[RetrievedItem], prompt_version: str) -> ModelResponse:
        if not self.settings.api_key:
            raise GatewayNotConfigured(
                "gateway mode 'deepseek' requires SOVBENCH_DEEPSEEK_API_KEY (never committed)"
            )
        t0 = time.perf_counter()
        prompt_hash = self._prompt_hash(prompt_version)
        system = self._system_prompt()
        bundle = format_evidence(evidence, budget=self.settings.token_budget)
        user = f"Question: {query.question}\n\nEvidence:\n{bundle.text}"
        body = {
            "model": self.settings.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": self.settings.temperature,
            "response_format": {"type": "json_object"},
            "stream": False,
        }
        if self.settings.thinking_enabled:
            body["thinking"] = {"type": "enabled"}
            body["reasoning_effort"] = self.settings.reasoning_effort

        payload, retries = self._post_with_retries(body)
        content = payload["choices"][0]["message"]["content"]
        parse_retries = 0
        while True:
            try:
                structured = _parse_structured(content)
                break
            except GatewayError:
                # Upstream occasionally returns a 200 with empty/garbled
                # content; retry a bounded number of times (recorded in the
                # trace) before failing the attempt honestly.
                parse_retries += 1
                if parse_retries > self.settings.max_retries:
                    raise
                time.sleep(1.0 * parse_retries)
                payload, _ = self._post_with_retries(body)
                content = payload["choices"][0]["message"]["content"]
        retries += parse_retries
        response_model_id = payload.get("model")
        request_id = payload.get("id")
        usage = payload.get("usage")
        attestation = attest_model(
            self.settings.model,
            response_model_id,
            self.settings.model_release,
            self.settings.attestation_mode,
        )
        if not attestation["ok"]:
            raise GatewayError(f"model attestation failed: {attestation['label']}")
        estimated_request = estimate_tokens(system) + estimate_tokens(user)
        estimated_response = estimate_tokens(content)
        resp = ModelResponse(
            structured=structured,
            model_id=self.settings.model,
            mode=self.mode,
            prompt_hash=prompt_hash,
            request_tokens=int((usage or {}).get("prompt_tokens", estimated_request)),
            response_tokens=int((usage or {}).get("completion_tokens", estimated_response)),
            retries=retries,
            latency_ms=(time.perf_counter() - t0) * 1000.0,
            response_model_id=response_model_id,
            request_id=request_id,
            raw={"provider_response": payload},
            usage=usage,
            attestation=attestation,
        )
        self._log(
            {
                "ts": self._now(),
                "gateway_mode": self.mode,
                "query_id": query.query_id,
                "model": self.settings.model,
                "response_model_id": response_model_id,
                "request_id": request_id,
                "prompt_hash": prompt_hash,
                "request_tokens": resp.request_tokens,
                "response_tokens": resp.response_tokens,
                "retries": resp.retries,
                "latency_ms": round(resp.latency_ms, 3),
                "usage": usage,
                "structured": structured,
            }
        )
        return resp

    def _post_with_retries(self, body: dict):
        retries = 0
        while True:
            try:
                return self._post(body), retries
            except GatewayRateLimit as exc:
                retries += 1
                if retries > self.settings.max_retries:
                    raise GatewayError(f"rate limited after {retries} attempts") from exc
                time.sleep(1.0 * retries)
            except urllib.error.URLError as exc:
                retries += 1
                if retries > self.settings.max_retries:
                    raise GatewayError(f"gateway request failed after {retries} attempts: {exc}") from exc
                time.sleep(0.5 * retries)

    def _post(self, body: dict):
        base = (self.settings.gateway_url or self.settings.base_url).rstrip("/")
        url = base + "/chat/completions"
        data = json.dumps(body).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.settings.api_key}",
        }
        if self.settings.gateway_url:
            if self.settings.identity_run_id:
                headers["X-Sovbench-Run-Id"] = self.settings.identity_run_id
            if self.settings.identity_provider_id:
                headers["X-Sovbench-Provider-Id"] = self.settings.identity_provider_id
        req = urllib.request.Request(
            url,
            data=data,
            headers=headers,
        )
        try:
            with urllib.request.urlopen(req, timeout=self.settings.timeout_s) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 500, 502, 503, 504):
                raise GatewayRateLimit(f"HTTP {exc.code}") from exc
            raise GatewayError(f"HTTP {exc.code}: {exc.read()[:500]!r}") from exc
        return payload


def _parse_structured(content: str) -> dict:
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].lstrip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise GatewayError(f"reader returned invalid JSON: {content[:200]!r}") from exc
    if not isinstance(data, dict):
        raise GatewayError(f"reader returned non-object JSON: {content[:200]!r}")
    expected = {"answer", "confidence", "abstain", "evidence_ids"}
    if set(data) != expected:
        raise GatewayError(f"reader JSON keys must be exactly {sorted(expected)}")
    if not isinstance(data["abstain"], bool):
        raise GatewayError("reader abstain must be a JSON boolean")
    confidence = data["confidence"]
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0.0 <= confidence <= 1.0:
        raise GatewayError("reader confidence must be a number from 0.0 to 1.0")
    answer = data["answer"]
    if answer is not None and not isinstance(answer, str):
        raise GatewayError("reader answer must be a string or null")
    if data["abstain"] and answer is not None:
        raise GatewayError("reader answer must be null when abstain is true")
    if not data["abstain"] and (not isinstance(answer, str) or not answer.strip()):
        raise GatewayError("reader answer must be a non-empty string when abstain is false")
    evidence_ids = data["evidence_ids"]
    if not isinstance(evidence_ids, list) or any(not isinstance(value, str) or not value for value in evidence_ids):
        raise GatewayError("reader evidence_ids must be a list of non-empty strings")
    if len(evidence_ids) != len(set(evidence_ids)):
        raise GatewayError("reader evidence_ids must not contain duplicates")
    return {"answer": answer, "confidence": float(confidence), "abstain": data["abstain"], "evidence_ids": evidence_ids}


def get_gateway(settings: Settings, clock: Optional[BenchmarkClock] = None, log_path: Optional[Path] = None):
    if settings.gateway_mode == "offline":
        return OfflineGateway(settings, clock=clock, log_path=log_path)
    if settings.gateway_mode == "deepseek":
        return DeepSeekGateway(settings, clock=clock, log_path=log_path)
    raise GatewayError(f"unknown gateway mode: {settings.gateway_mode}")
