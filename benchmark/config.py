"""Configuration loading: config/default.toml overridden by environment."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Settings:
    gateway_mode: str = "offline"
    model: str = "deepseek-v4-flash"
    model_release: str = "DeepSeek-V4-Flash-0731"
    base_url: str = "https://api.deepseek.com"
    gateway_url: str = ""  # local policy-gated proxy; empty means direct API access
    api_key: str = ""
    max_retries: int = 2
    temperature: float = 0.0
    thinking_enabled: bool = True
    reasoning_effort: str = "high"
    attestation_mode: str = "rolling"  # "rolling" labels; "strict" requires release evidence
    identity_run_id: str = ""  # sent to the gateway proxy when gateway_url is set
    identity_provider_id: str = ""
    timeout_s: float = 60.0
    prompt_path: Path = REPO_ROOT / "prompts" / "reader-v1.md"
    prompt_version: str = "v1"
    token_budget: int = 2048
    track: str = "controlled"
    clock_start: str = "2026-08-01T00:00:00Z"
    corpus_dir: Path = REPO_ROOT / "datasets" / "dev" / "personal"
    gold_path: Path = REPO_ROOT / "datasets" / "dev" / "personal" / "ground_truth.jsonl"
    run_root: Path = REPO_ROOT / "runs"
    report_root: Path = REPO_ROOT / "reports"
    docker_compose: Path = REPO_ROOT / "docker" / "compose.yml"


def _get(cfg: dict, section: str, key: str, default):
    return cfg.get(section, {}).get(key, default)


def load_settings(config_path: Path | None = None) -> Settings:
    path = Path(config_path) if config_path else REPO_ROOT / "config" / "default.toml"
    cfg: dict = {}
    if path.exists():
        with open(path, "rb") as f:
            cfg = tomllib.load(f)
    s = Settings()

    s.gateway_mode = os.environ.get("SOVBENCH_GATEWAY_MODE", _get(cfg, "gateway", "mode", s.gateway_mode))
    s.model = os.environ.get("SOVBENCH_DEEPSEEK_MODEL", _get(cfg, "gateway", "model", s.model))
    s.model_release = os.environ.get(
        "SOVBENCH_DEEPSEEK_MODEL_RELEASE", _get(cfg, "gateway", "model_release", s.model_release)
    )
    s.base_url = os.environ.get("SOVBENCH_DEEPSEEK_BASE_URL", _get(cfg, "gateway", "base_url", s.base_url))
    s.gateway_url = os.environ.get("SOVBENCH_GATEWAY_URL", _get(cfg, "gateway", "gateway_url", s.gateway_url))
    s.api_key = os.environ.get("SOVBENCH_DEEPSEEK_API_KEY", _get(cfg, "gateway", "api_key", s.api_key))
    s.max_retries = int(os.environ.get("SOVBENCH_MAX_RETRIES", _get(cfg, "gateway", "max_retries", s.max_retries)))
    s.temperature = float(os.environ.get("SOVBENCH_TEMPERATURE", _get(cfg, "gateway", "temperature", s.temperature)))
    s.thinking_enabled = str(
        os.environ.get("SOVBENCH_THINKING_ENABLED", _get(cfg, "gateway", "thinking_enabled", s.thinking_enabled))
    ).lower() in {"1", "true", "yes", "on"}
    s.reasoning_effort = os.environ.get(
        "SOVBENCH_REASONING_EFFORT", _get(cfg, "gateway", "reasoning_effort", s.reasoning_effort)
    )
    s.attestation_mode = os.environ.get(
        "SOVBENCH_ATTESTATION_MODE", _get(cfg, "gateway", "attestation_mode", s.attestation_mode)
    )
    s.identity_run_id = os.environ.get("SOVBENCH_IDENTITY_RUN_ID", _get(cfg, "gateway", "identity_run_id", s.identity_run_id))
    s.identity_provider_id = os.environ.get(
        "SOVBENCH_IDENTITY_PROVIDER_ID", _get(cfg, "gateway", "identity_provider_id", s.identity_provider_id)
    )
    s.timeout_s = float(os.environ.get("SOVBENCH_TIMEOUT_S", _get(cfg, "gateway", "timeout_s", s.timeout_s)))
    s.prompt_version = os.environ.get("SOVBENCH_PROMPT_VERSION", _get(cfg, "reader", "prompt_version", s.prompt_version))
    s.token_budget = int(
        os.environ.get(
            "SOVBENCH_TOKEN_BUDGET",
            _get(cfg, "benchmark", "token_budget", _get(cfg, "reader", "token_budget", s.token_budget)),
        )
    )
    s.track = os.environ.get("SOVBENCH_TRACK", _get(cfg, "benchmark", "track", s.track))
    s.clock_start = os.environ.get("SOVBENCH_CLOCK_START", _get(cfg, "benchmark", "clock_start", s.clock_start))

    prompt_rel = _get(cfg, "reader", "prompt_path", None)
    if prompt_rel:
        s.prompt_path = Path(os.environ.get("SOVBENCH_PROMPT_PATH", str(REPO_ROOT / prompt_rel)))
    else:
        s.prompt_path = Path(os.environ.get("SOVBENCH_PROMPT_PATH", str(s.prompt_path)))

    corpus_rel = _get(cfg, "paths", "corpus_dir", None)
    if corpus_rel:
        s.corpus_dir = Path(os.environ.get("SOVBENCH_CORPUS_DIR", str(REPO_ROOT / corpus_rel)))
    gold_rel = _get(cfg, "paths", "gold_path", None)
    if gold_rel:
        s.gold_path = Path(os.environ.get("SOVBENCH_GOLD_PATH", str(REPO_ROOT / gold_rel)))
    run_rel = _get(cfg, "paths", "run_root", None)
    if run_rel:
        s.run_root = Path(os.environ.get("SOVBENCH_RUN_ROOT", str(REPO_ROOT / run_rel)))
    report_rel = _get(cfg, "paths", "report_root", None)
    if report_rel:
        s.report_root = Path(os.environ.get("SOVBENCH_REPORT_ROOT", str(REPO_ROOT / report_rel)))
    compose_rel = _get(cfg, "paths", "docker_compose", None)
    if compose_rel:
        s.docker_compose = Path(os.environ.get("SOVBENCH_DOCKER_COMPOSE", str(REPO_ROOT / compose_rel)))
    return s
