"""Cost-gated reader-protocol pilot (Task 4).

The pilot calibrates the stateless reader on provider-independent cases before
any memory provider is scored. ``dry-run`` mode exercises the full plumbing
with the offline stub at $0. ``live`` mode routes through the policy-gated
proxy and the official DeepSeek API, and refuses to run until the cost gate is
explicitly approved (SOVBENCH_PILOT_COST_APPROVED=1) and a key is supplied.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import threading
import time
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Callable

from benchmark.config import Settings, load_settings
from benchmark.events import Query
from benchmark.gateway.ledger import Ledger
from benchmark.gateway.policy import GatewayPolicy, estimate_tokens
from benchmark.gateway.server import create_server
from benchmark.model_gateway import get_gateway
from benchmark.providers import RetrievedItem
from benchmark.token_budget import format_evidence

REPO_ROOT = Path(__file__).resolve().parent.parent
PILOT_DIR = REPO_ROOT / "experiments" / "reader-pilot"

CASE_KINDS = ("oracle_answerable", "no_memory_abstention", "authority_conflict", "temporal_validity")
EXPECTED_CASE_COUNTS = {
    "oracle_answerable": 8,
    "no_memory_abstention": 8,
    "authority_conflict": 2,
    "temporal_validity": 2,
}
EXPECTED_TOTAL = 20
SELECTION_HIERARCHY = ("json_valid", "oracle_correct", "abstain_correct", "evidence_id_valid", "mean_tokens")


class PilotGateError(RuntimeError):
    """Raised when the live pilot's cost gate has not been explicitly approved."""


@dataclass(frozen=True)
class PilotCase:
    case_id: str
    kind: str
    question: str
    as_of: str
    principal: str
    evidence: tuple[dict, ...]
    expected: dict


def validate_cases(cases: list[PilotCase]) -> None:
    if len(cases) != EXPECTED_TOTAL:
        raise ValueError(f"pilot requires {EXPECTED_TOTAL} cases, found {len(cases)}")
    counts: dict[str, int] = {}
    for case in cases:
        if case.kind not in CASE_KINDS:
            raise ValueError(f"{case.case_id}: unknown kind {case.kind!r}")
        if not case.case_id or not case.question or not case.as_of:
            raise ValueError(f"{case.case_id}: missing case_id/question/as_of")
        if not isinstance(case.expected, dict) or "abstain" not in case.expected:
            raise ValueError(f"{case.case_id}: expected must carry abstain")
        counts[case.kind] = counts.get(case.kind, 0) + 1
    if counts != EXPECTED_CASE_COUNTS:
        raise ValueError(f"case kind counts must be {EXPECTED_CASE_COUNTS}, found {counts}")


def load_cases(path: Path | str) -> list[PilotCase]:
    records = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    cases = [
        PilotCase(
            case_id=str(record["case_id"]),
            kind=str(record["kind"]),
            question=str(record["question"]),
            as_of=str(record["as_of"]),
            principal=str(record.get("principal", "user_001")),
            evidence=tuple(record.get("evidence", [])),
            expected=record["expected"],
        )
        for record in records
    ]
    validate_cases(cases)
    return cases


def load_configs(path: Path | str) -> list[dict]:
    import tomllib

    with open(path, "rb") as handle:
        data = tomllib.load(handle)
    configs = []
    for key, value in data.get("settings", {}).items():
        config = dict(value)
        config.setdefault("name", key)
        configs.append(config)
    if not configs:
        raise ValueError(f"no [settings.*] variants found in {path}")
    return configs


def normalize_answer(value: str) -> str:
    import re

    value = value.lower()
    value = re.sub(r"[^a-z0-9 ]", " ", value)
    return " ".join(value.split())


def _evidence_items(case: PilotCase) -> list[RetrievedItem]:
    metadata_keys = ("authority", "source", "available_at", "valid_from", "valid_to", "subject", "principal")
    items = []
    for evidence in case.evidence:
        items.append(
            RetrievedItem(
                item_id=str(evidence["id"]),
                text=str(evidence["text"]),
                score=None,
                metadata={key: evidence.get(key) for key in metadata_keys if evidence.get(key) is not None},
            )
        )
    return items


def build_user_message(case: PilotCase, budget: int = 2048) -> str:
    bundle = format_evidence(_evidence_items(case), budget)
    return f"Question: {case.question}\n\nEvidence:\n{bundle.text}"


def score_case(case: PilotCase, structured: dict, provided_ids: set[str]) -> dict:
    abstain = bool(structured.get("abstain", False))
    answer = structured.get("answer")
    cited = set(structured.get("evidence_ids") or [])
    if case.kind == "no_memory_abstention":
        correct = abstain
    else:
        expected = case.expected.get("answer")
        correct = (
            not abstain
            and isinstance(answer, str)
            and normalize_answer(str(expected)) in normalize_answer(answer)
        )
    expected_cited = set(case.expected.get("evidence_ids") or [])
    evidence_valid = cited <= provided_ids
    if expected_cited:
        evidence_valid = evidence_valid and expected_cited <= cited
    return {
        "case_id": case.case_id,
        "kind": case.kind,
        "correct": correct,
        "evidence_id_valid": evidence_valid,
    }


def _attempt(gateway, case: PilotCase, budget: int, prompt_version: str) -> dict:
    query = Query(case.case_id, case.question, case.principal, "personal", case.as_of, "pilot")
    items = _evidence_items(case)
    provided_ids = {item.item_id for item in items}
    started = time.perf_counter()
    try:
        response = gateway.generate(query, items, prompt_version)
        structured = response.structured
        ok = True
        error_class = None
        request_tokens = int(getattr(response, "request_tokens", 0) or 0)
        response_tokens = int(getattr(response, "response_tokens", 0) or 0)
    except Exception as exc:  # noqa: BLE001 - every failure is recorded
        structured = {"abstain": False, "answer": None, "evidence_ids": []}
        ok = False
        error_class = type(exc).__name__
        request_tokens = 0
        response_tokens = 0
    latency_ms = round((time.perf_counter() - started) * 1000.0, 3)
    return {
        **score_case(case, structured, provided_ids),
        "ok": ok,
        "error_class": error_class,
        "request_tokens": request_tokens,
        "response_tokens": response_tokens,
        "latency_ms": latency_ms,
    }


def select_best(aggregates: list[dict]) -> tuple[str, str]:
    def key(aggregate: dict) -> tuple:
        return (
            -float(aggregate["json_valid"]),
            -float(aggregate["oracle_correct"]),
            -float(aggregate["abstain_correct"]),
            -float(aggregate["evidence_id_valid"]),
            float(aggregate["mean_tokens"]),
            str(aggregate["name"]),
        )

    best = min(aggregates, key=key)
    reason = f"selected by preregistered hierarchy: {', '.join(SELECTION_HIERARCHY)}"
    return best["name"], reason


def run_pilot(
    cases: list[PilotCase],
    configs: list[dict],
    gateway_factory: Callable[[dict], object],
    repeats: int = 3,
    budget: int = 2048,
    prompt_version: str = "v1",
    mode: str = "dry-run",
) -> dict:
    by_id = {case.case_id: case for case in cases}
    attempts: dict[str, dict[str, list[dict]]] = {}
    for config in configs:
        gateway = gateway_factory(config)
        per_case: dict[str, list[dict]] = {}
        for case in cases:
            per_case[case.case_id] = [_attempt(gateway, case, budget, prompt_version) for _ in range(repeats)]
        attempts[config["name"]] = per_case

    aggregates = []
    for name, per_case in attempts.items():
        all_attempts = [attempt for case_attempts in per_case.values() for attempt in case_attempts]
        oracle_attempts = [
            attempt for case_id, case_attempts in per_case.items() for attempt in case_attempts
            if by_id[case_id].kind == "oracle_answerable"
        ]
        abstain_attempts = [
            attempt for case_id, case_attempts in per_case.items() for attempt in case_attempts
            if by_id[case_id].kind == "no_memory_abstention"
        ]
        nondeterministic = any(
            len({attempt["ok"] for attempt in case_attempts}) > 1
            or len({attempt["correct"] for attempt in case_attempts}) > 1
            for case_attempts in per_case.values()
        )
        aggregates.append(
            {
                "name": name,
                "json_valid": round(sum(attempt["ok"] for attempt in all_attempts) / len(all_attempts), 4),
                "oracle_correct": round(
                    sum(attempt["correct"] for attempt in oracle_attempts) / len(oracle_attempts), 4
                ),
                "abstain_correct": round(
                    sum(attempt["correct"] for attempt in abstain_attempts) / len(abstain_attempts), 4
                ),
                "evidence_id_valid": round(
                    sum(attempt["evidence_id_valid"] for attempt in all_attempts) / len(all_attempts), 4
                ),
                "mean_tokens": round(
                    sum(attempt["request_tokens"] + attempt["response_tokens"] for attempt in all_attempts)
                    / len(all_attempts),
                    1,
                ),
                "total_tokens": sum(
                    attempt["request_tokens"] + attempt["response_tokens"] for attempt in all_attempts
                ),
                "mean_latency_ms": round(
                    sum(attempt["latency_ms"] for attempt in all_attempts) / len(all_attempts), 2
                ),
                "errors": sorted(
                    {attempt["error_class"] for attempt in all_attempts if attempt["error_class"]}
                ),
                "nondeterministic": nondeterministic,
            }
        )

    selected, reason = select_best(aggregates)
    prompt_path = REPO_ROOT / "prompts" / "reader-v1.md"
    prompt_hash = hashlib.sha256(prompt_path.read_bytes()).hexdigest()
    nondeterministic = any(aggregate["nondeterministic"] for aggregate in aggregates)
    return {
        "mode": mode,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "repeats": repeats,
        "budget": budget,
        "prompt_version": prompt_version,
        "prompt_hash": prompt_hash,
        "configs": aggregates,
        "selection": {"name": selected, "reason": reason},
        "nondeterminism": {
            "detected": nondeterministic,
            "recommended_repeats": 5 if nondeterministic else 3,
        },
    }


def estimate_cost(
    cases: list[PilotCase],
    configs: list[dict],
    repeats: int,
    price_per_million_input: float,
    price_per_million_output: float,
    thinking_output_tokens: int,
    plain_output_tokens: int,
    system_prompt: str,
) -> dict:
    requests = len(cases) * len(configs) * repeats
    input_tokens = sum(
        estimate_tokens(system_prompt) + estimate_tokens(build_user_message(case))
        for case in cases
    ) * len(configs) * repeats
    output_tokens = sum(
        (thinking_output_tokens if config.get("thinking_enabled") else plain_output_tokens)
        for config in configs
    ) * len(cases) * repeats
    max_cost = (
        input_tokens / 1_000_000 * price_per_million_input
        + output_tokens / 1_000_000 * price_per_million_output
    )
    return {
        "requests": requests,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "max_cost_usd": round(max_cost, 4),
        "price_per_million_input": price_per_million_input,
        "price_per_million_output": price_per_million_output,
    }


def check_live_gate(settings: Settings, approved_env: dict | None = None) -> None:
    env = os.environ if approved_env is None else approved_env
    if not settings.api_key:
        raise PilotGateError("live pilot requires SOVBENCH_DEEPSEEK_API_KEY (never committed)")
    if env.get("SOVBENCH_PILOT_COST_APPROVED") != "1":
        raise PilotGateError(
            "refusing live pilot: set SOVBENCH_PILOT_COST_APPROVED=1 after approving the cost "
            "estimate in experiments/reader-pilot/protocol.md"
        )


def live_settings(base: Settings, proxy_url: str, config: dict) -> Settings:
    return replace(
        base,
        gateway_mode="deepseek",
        model=base.model,
        gateway_url=proxy_url,
        thinking_enabled=bool(config.get("thinking_enabled")),
        reasoning_effort=str(config.get("reasoning_effort", "high")),
        temperature=float(config.get("temperature", 0.0)),
        identity_run_id=f"reader-pilot-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        identity_provider_id="reader-pilot",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Cost-gated reader-protocol pilot.")
    parser.add_argument("--mode", choices=("dry-run", "live"), default="dry-run")
    parser.add_argument("--cases", type=Path, default=PILOT_DIR / "cases.jsonl")
    parser.add_argument("--configs", type=Path, default=PILOT_DIR / "configs.toml")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--budget", type=int, default=2048)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    cases = load_cases(args.cases)
    configs = load_configs(args.configs)
    base = load_settings()

    if args.mode == "live":
        check_live_gate(base)
        policy = GatewayPolicy.load(REPO_ROOT / "config" / "gateway-policy.toml")
        ledger = Ledger(PILOT_DIR / "ledger.jsonl")
        proxy = create_server(
            policy=policy,
            ledger=ledger,
            upstream_url="https://api.deepseek.com/chat/completions",
            api_key=base.api_key,
            port=0,
        )
        thread = threading.Thread(target=proxy.serve_forever, daemon=True)
        thread.start()
        proxy_url = f"http://127.0.0.1:{proxy.server_port}"

        def factory(config: dict):
            return get_gateway(live_settings(base, proxy_url, config))
    else:
        proxy = None

        def factory(config: dict):
            return get_gateway(load_settings())

    result = run_pilot(
        cases=cases,
        configs=configs,
        gateway_factory=factory,
        repeats=args.repeats,
        budget=args.budget,
        mode=args.mode,
    )
    prompt_text = (REPO_ROOT / "prompts" / "reader-v1.md").read_text(encoding="utf-8")
    result["cost_estimate"] = estimate_cost(
        cases=cases,
        configs=configs,
        repeats=args.repeats,
        price_per_million_input=0.14,
        price_per_million_output=0.28,
        thinking_output_tokens=8000,
        plain_output_tokens=400,
        system_prompt=prompt_text,
    )

    out = args.out or PILOT_DIR / "results" / f"pilot-{args.mode}-{result['generated_at'].replace(':', '')}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"pilot mode={args.mode} repeats={args.repeats}")
    for aggregate in result["configs"]:
        print(
            f"  {aggregate['name']:<24} json={aggregate['json_valid']} oracle={aggregate['oracle_correct']} "
            f"abstain={aggregate['abstain_correct']} evidence={aggregate['evidence_id_valid']} "
            f"tokens={aggregate['mean_tokens']} nondet={aggregate['nondeterministic']}"
        )
    print(f"selection: {result['selection']['name']} ({result['selection']['reason']})")
    print(f"cost estimate: ${result['cost_estimate']['max_cost_usd']} max for {result['cost_estimate']['requests']} requests")
    print(f"result: {out}")
    if proxy is not None:
        proxy.shutdown()
        proxy.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
