"""Freeze and verify the Phase 1 controlled protocol (plan Task 13).

Writes ``protocols/v1/config-freeze.json`` with deterministic content hashes
for the code commit, lock files, provider images, configs, schemas, DEV
corpus, reader prompt, scorer modules, protocol documents, and the unopened
hidden TEST commitment. ``--verify`` re-checks the committed freeze against
the working tree; ``--dry-run`` additionally runs the $0 offline plumbing
suite on DEV and requires zero manual intervention.

Design rules:
- Content groups are hashed from sorted relative paths with SHA-256, so the
  freeze is deterministic across machines and reruns.
- The freeze commit is recorded as metadata. After the freeze commit lands,
  the recorded commit intentionally differs from HEAD; verification compares
  content groups, not the commit id.
- Nothing here reads the hidden TEST gold, opens any pack for scoring, or
  performs a paid API call. Hidden packs are only verified against their
  committed SHA-256 commitments.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FREEZE_PATH = REPO_ROOT / "protocols" / "v1" / "config-freeze.json"
PROTOCOL_DIR = REPO_ROOT / "protocols" / "v1"
COMMITMENT_PATH = REPO_ROOT / "datasets" / "commitments" / "test-v1.json"
PACKS_DIR = REPO_ROOT / "scorer_private" / "test-v1"
PILOT_RESULTS_DIR = REPO_ROOT / "experiments" / "reader-pilot" / "results"
DRY_RUN_COMMAND = [sys.executable, str(REPO_ROOT / "scripts" / "run_phase0.py")]

SCHEMA = "sovbench/protocol-freeze/1"

# Files created by the freeze task itself. They are uncommitted at
# generation time by design: the freeze records the exact bytes that the
# freeze commit then adds. Any uncommitted change OUTSIDE this set refuses
# the freeze.
PENDING_FREEZE_PATHS = (
    "protocols/",
    "scripts/freeze_protocol.py",
    "tests/test_protocol_freeze.py",
    "docs/progress/implementation.json",
)

# Provider image -> local image reference used for digest pinning. Entries
# whose image has not been built yet are recorded with upstream pins only.
KNOWN_IMAGES = {
    "optmem": "sovbench-optmem:1fb164c",
}

# Content groups hashed into the freeze. Relative paths are sorted and hashed
# as "<rel>:<sha256>" lines; the group digest is the sha256 of that listing.
CONTENT_GROUPS = {
    "lock": [
        "pyproject.toml",
        "uv.lock",
        ".python-version",
    ],
    "configs": [
        "config/default.toml",
        "config/gateway-policy.toml",
        "config/providers/bm25-pure.toml",
        "config/providers/full-context.toml",
        "providers/optmem/config.toml",
        "providers/gbrain/config.toml",
        "providers/mem0/config.toml",
        "providers/hindsight/config.toml",
    ],
    "schemas": [
        "schemas/event.schema.json",
        "schemas/ground-truth.schema.json",
        "schemas/manifest.schema.json",
        "schemas/provider-capabilities.schema.json",
        "schemas/query.schema.json",
        "schemas/result-bundle.schema.json",
    ],
    "dev": [
        "datasets/dev/personal/events.jsonl",
        "datasets/dev/personal/ground_truth.jsonl",
        "datasets/dev/personal/queries.jsonl",
        "datasets/dev/personal/dataset-card.md",
    ],
    "prompt": [
        "prompts/reader-v1.md",
    ],
    "scorer": [
        "benchmark/scorer.py",
        "benchmark/metrics.py",
        "benchmark/statistics.py",
        "benchmark/validation.py",
    ],
    "protocol": [
        "protocols/v1/personal-controlled.md",
        "protocols/v1/analysis-plan.md",
    ],
}

# Frozen reader settings (verified by the approved live pilot, 2026-08-06).
FROZEN_READER = {
    "model": "deepseek-v4-flash",
    "expected_release": "DeepSeek-V4-Flash-0731",
    "attestation_mode": "rolling",
    "thinking_enabled": False,
    "reasoning_effort": "none",
    "temperature": 0.0,
    "token_budget": 2048,
    "prompt_version": "v1",
    "repeats": 3,
    "clock_start": "2026-08-01T00:00:00Z",
}

PRIMARY_OUTCOMES = [
    "complete_chain_at_5",
    "typed_answer_correctness",
    "calibrated_abstention",
    "cross_principal_leakage",
    "deletion_persistence",
    "export_round_trip_fidelity",
]

CONTROLS = [
    {"name": "no-memory", "role": "abstention control"},
    {"name": "oracle", "role": "retrieval integrity control"},
    {"name": "random-retrieval", "role": "chance-level negative control"},
    {"name": "full-context", "role": "no-retrieval cost control"},
    {"name": "bm25-pure", "role": "lexical baseline"},
    {"name": "bm25-sqlite-fts", "role": "lexical baseline"},
]

PROVIDERS = [
    {
        "name": "optmem",
        "upstream": "https://github.com/VictorTaelin/OptMem",
        "upstream_commit": "1fb164cf39028047781f72ac3bb1e5a691c1dcb0",
        "upstream_version": "0.1.0 (pinned script)",
        "license": "none-present (all rights reserved; gitignored local install)",
        "telemetry": "none",
        "network_needs": [],
        "notes": "append-only upstream: deletion-persistence outcome is unsupported; recorded, not simulated",
    },
    {
        "name": "gbrain",
        "upstream": "https://github.com/garrytan/gbrain",
        "upstream_commit": "15b9863d13635d173562a54f55a1d388bfcf546b",
        "upstream_version": "0.42.73.2",
        "license": "MIT",
        "telemetry": "none",
        "network_needs": [],
        "notes": "controlled config init --pglite --no-embedding: keyword/hybrid only, no external keys",
    },
    {
        "name": "mem0",
        "upstream": "https://github.com/mem0ai/mem0",
        "upstream_commit": "3f39fba28f7781aaf581f64a4af39d017af65835",
        "upstream_version": "2.0.17",
        "license": "Apache-2.0",
        "telemetry": "disabled (MEM0_TELEMETRY=false set before import; runtime denial verified)",
        "network_needs": [],
        "notes": "add(infer=False), local chroma + fastembed BAAI/bge-small-en-v1.5; semantic-only retrieval",
    },
    {
        "name": "hindsight",
        "upstream": "https://github.com/vectorize-io/hindsight",
        "upstream_commit": "797faf7981ce9332e2ce7c922471b72b506b4065",
        "upstream_version": "0.8.6",
        "license": "MIT",
        "telemetry": "none observed (opentelemetry metrics only)",
        "network_needs": [],
        "notes": "LLM-gated reflection/consolidation stay OFF in the controlled config; live verification is gated on the Phase 1 environment (Postgres+pgvector)",
    },
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def hash_group(repo_root: Path, rel_files: list[str]) -> tuple[dict[str, str], str]:
    """Hash one content group: sorted '<rel>:<sha256>' lines -> group digest."""
    lines: list[str] = []
    per_file: dict[str, str] = {}
    for rel in sorted(rel_files):
        path = repo_root / rel
        if not path.exists():
            raise FileNotFoundError(f"freeze group file missing: {rel}")
        digest = sha256_file(path)
        per_file[rel] = digest
        lines.append(f"{rel}:{digest}")
    return per_file, hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def collect_groups(repo_root: Path | None = None) -> dict:
    root = Path(repo_root) if repo_root else REPO_ROOT
    groups: dict = {}
    for name, rel_files in CONTENT_GROUPS.items():
        per_file, digest = hash_group(root, rel_files)
        groups[name] = {"digest": digest, "files": per_file}
    return groups


def git_info(repo_root: Path | None = None) -> dict:
    root = Path(repo_root) if repo_root else REPO_ROOT

    def run(args: list[str]) -> str:
        return (
            subprocess.run(
                ["git", "-C", str(root), *args],
                capture_output=True,
                text=True,
                check=True,
            )
            .stdout.strip()
        )

    status = run(["status", "--porcelain"])
    return {
        "commit": run(["rev-parse", "HEAD"]),
        "describe": run(["describe", "--tags", "--always"]),
        "tree_clean": not status,
        "uncommitted": [line for line in status.splitlines() if line],
    }


def image_digests() -> dict[str, str]:
    """Resolve known provider images via `docker images --digests`.

    Returns a map of provider name -> digest for images present locally.
    Missing images (not built yet) are reported separately by callers.
    """
    out: dict[str, str] = {}
    try:
        result = subprocess.run(
            ["docker", "images", "--digests", "--format", "{{.Repository}}:{{.Tag}} {{.Digest}}"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return out
    if result.returncode != 0:
        return out
    by_ref: dict[str, str] = {}
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) == 2:
            by_ref[parts[0]] = parts[1]
    for provider, ref in KNOWN_IMAGES.items():
        if ref in by_ref:
            out[provider] = by_ref[ref]
    return out


def test_commitment_status(repo_root: Path | None = None) -> dict:
    root = Path(repo_root) if repo_root else REPO_ROOT
    sys.path.insert(0, str(root))
    from benchmark.datasets.commitment import load_commitments, verify_pack

    commitment = load_commitments(COMMITMENT_PATH)
    packs: dict = {}
    errors: list[str] = []
    for pack_name, pack_commitment in sorted(commitment.get("packs", {}).items()):
        pack_dir = PACKS_DIR / pack_name
        if not pack_dir.exists():
            errors.append(f"{pack_name}: pack directory missing (unopened TEST not generated?)")
            continue
        pack_errors = verify_pack(pack_dir, pack_commitment)
        packs[pack_name] = {
            "aggregate": pack_commitment.get("aggregate"),
            "queries": pack_commitment.get("summary", {}).get("queries"),
            "verified": not pack_errors,
            "errors": pack_errors,
        }
        errors.extend(f"{pack_name}: {error}" for error in pack_errors)
    return {
        "commitment_path": COMMITMENT_PATH.relative_to(root).as_posix(),
        "commitment_sha256": sha256_file(COMMITMENT_PATH),
        "packs_present": all(pack_dir.exists() for pack_dir in [PACKS_DIR / p for p in commitment.get("packs", {})]),
        "verified": not errors,
        "packs": packs,
        "errors": errors,
    }


def dev_corpus_validation(repo_root: Path | None = None) -> dict:
    root = Path(repo_root) if repo_root else REPO_ROOT
    sys.path.insert(0, str(root))
    from benchmark.events import load_events, load_ground_truth, load_queries
    from benchmark.validation import validate_corpus

    events = load_events(root / "datasets" / "dev" / "personal" / "events.jsonl")
    queries = load_queries(root / "datasets" / "dev" / "personal" / "queries.jsonl")
    gold = load_ground_truth(root / "datasets" / "dev" / "personal" / "ground_truth.jsonl")
    result = validate_corpus(events, queries, gold)
    return {
        "events": len(events),
        "queries": len(queries),
        "gold_rows": len(gold),
        "passed": result.passed,
        "errors": list(result.errors),
    }


def pilot_usage(repo_root: Path | None = None) -> dict:
    """Per-request token averages from the approved live pilot (2026-08-06)."""
    root = Path(repo_root) if repo_root else REPO_ROOT
    results = sorted((PILOT_RESULTS_DIR).glob("pilot-live-*.json"))
    if not results:
        raise FileNotFoundError("no pilot-live-*.json result found; cannot estimate Phase 1 cost")
    payload = json.loads(results[-1].read_text(encoding="utf-8"))
    requests = int(payload.get("cost_estimate", {}).get("requests", 0))
    input_tokens = 97119
    output_tokens = 43450
    recorded_total = sum(int(cfg.get("total_tokens", 0)) for cfg in payload.get("configs", []))
    if requests != 180 or recorded_total != input_tokens + output_tokens:
        raise RuntimeError(
            f"pilot usage in {results[-1].name} disagrees with committed actuals: "
            f"requests={requests} total_tokens={recorded_total}"
        )
    return {
        "source": results[-1].name,
        "requests": requests,
        "actual_cost_usd": 0.0258,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }


def cost_estimate(test_queries: int = 192, repeats: int = 3, usage: dict | None = None) -> dict:
    """Phase 1 reader cost from pilot usage, plus a budget-saturating worst case.

    Pilot actuals: 180 requests, 97,119 input + 43,450 output tokens
    (USD 0.0258 at $0.14/$0.28 per million). Per-request averages:
    ~539.6 input, ~241.4 output.
    Worst case: 2,600 input tokens (2048-token evidence budget + prompt) and
    the full 2,048-token output budget per request.
    """
    usage = usage if usage is not None else pilot_usage()
    requests = test_queries * repeats
    per_req_input = usage["input_tokens"] / usage["requests"]
    per_req_output = usage["output_tokens"] / usage["requests"]
    expected_usd = (
        requests * per_req_input * 0.14 + requests * per_req_output * 0.28
    ) / 1_000_000
    worst_usd = requests * (2600 * 0.14 + 2048 * 0.28) / 1_000_000
    return {
        "test_queries": test_queries,
        "repeats": repeats,
        "requests": requests,
        "price_per_million_input": 0.14,
        "price_per_million_output": 0.28,
        "basis": "pilot actuals 2026-08-06 (180 requests, USD 0.0258)",
        "expected_usd": round(expected_usd, 4),
        "worst_case_usd": round(worst_usd, 4),
        "ceiling_usd_per_run": 1.0,
        "ceiling_usd_global": 10.0,
        "provider_native_model_calls_usd": 0.0,
        "note": "controlled track makes no provider-native model calls; gateway ceilings fail closed",
    }


def build_freeze(
    repo_root: Path | None = None,
    images: dict | None = None,
    git: dict | None = None,
    pending_allowed: tuple[str, ...] = PENDING_FREEZE_PATHS,
) -> dict:
    root = Path(repo_root) if repo_root else REPO_ROOT
    sys.path.insert(0, str(root))
    git_record = git if git is not None else git_info(root)
    uncommitted = [
        line for line in git_record.get("uncommitted", []) if not _is_pending(line, pending_allowed)
    ]
    if uncommitted:
        raise RuntimeError(
            "refusing to freeze a dirty tree; commit or stash first: "
            + "; ".join(uncommitted)
        )
    git_record["tree_clean"] = not uncommitted
    git_record["pending_freeze_paths"] = sorted(
        {line[3:].strip() for line in git_record.get("uncommitted", []) if _is_pending(line, pending_allowed)}
    )
    resolved_images = images if images is not None else image_digests()
    groups = collect_groups(root)
    prompt_file = root / "prompts" / "reader-v1.md"
    from benchmark import hashing

    prompt_digest = hashing.sha256_text(hashing.sha256_file(prompt_file) + "|" + FROZEN_READER["prompt_version"])
    prompt_file_sha256 = sha256_file(prompt_file)
    commitment = test_commitment_status(root)
    dev = dev_corpus_validation(root)
    if not dev["passed"]:
        raise RuntimeError("DEV corpus validation failed: " + "; ".join(dev["errors"]))
    if not commitment["verified"]:
        raise RuntimeError("hidden TEST commitment verification failed: " + "; ".join(commitment["errors"]))
    cost = cost_estimate()
    image_record = {
        provider: {"reference": ref, "digest": resolved_images.get(provider, "not-built")}
        for provider, ref in KNOWN_IMAGES.items()
    }
    return {
        "schema": SCHEMA,
        "protocol_version": "v1",
        "track": "controlled",
        "frozen_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tag": "protocol-v1-freeze",
        "git": git_record,
        "reader": FROZEN_READER,
        "reader_prompt_hash": prompt_digest,
        "prompt_file_sha256": prompt_file_sha256,
        "hashes": groups,
        "images": image_record,
        "dev_corpus": dev,
        "test_commitment": commitment,
        "dataset": {
            "dev": {"events": dev["events"], "queries": dev["queries"]},
            "test": {"packs": 3, "queries_per_pack": 64, "queries_total": 192},
        },
        "participants": {
            "controls": CONTROLS,
            "providers": PROVIDERS,
            "registrations": {
                "registry.json_baselines": ["bm25-pure", "bm25-sqlite-fts", "full-context"],
                "controls_not_registered": ["no-memory", "oracle", "random-retrieval"],
            },
        },
        "primary_outcomes": PRIMARY_OUTCOMES,
        "thresholds": {
            "oracle_recall_at_5_required": 1.0,
            "oracle_reader_accuracy_required": 0.95,
            "no_memory_abstain_accuracy_required": 1.0,
            "random_recall_at_5_band": [0.0, 0.25],
            "leakage_required_zero": ["cross_principal_evidence_total", "deleted_evidence_total"],
            "export_parity_min_dev": 0.98,
            "practical_delta_min": 0.05,
            "mcnemar_min_discordant_pairs": 5,
            "alpha": 0.05,
            "bootstrap_resamples": 10000,
            "bootstrap_seed": 20260805,
        },
        "cost": cost,
        "dry_run": {"command": "scripts/run_phase0.py", "cost_usd": 0.0, "reader": "offline stub"},
    }


def _is_pending(line: str, pending_allowed: tuple[str, ...]) -> bool:
    """True when a porcelain status line belongs to the freeze commit itself."""
    path = line[3:].strip()
    return any(path == prefix or path.startswith(prefix) for prefix in pending_allowed)


def verify_freeze(
    repo_root: Path | None = None,
    freeze_path: Path | None = None,
    images: dict | None = None,
    require_images: bool = False,
) -> list[str]:
    """Recompute content hashes and compare against the committed freeze.

    The recorded commit is informational; content groups (lock, configs,
    schemas, dev, prompt, scorer, protocol) must match exactly.
    """
    root = Path(repo_root) if repo_root else REPO_ROOT
    path = Path(freeze_path) if freeze_path else FREEZE_PATH
    if not path.exists():
        return [f"freeze file missing: {path}"]
    freeze = json.loads(path.read_text(encoding="utf-8"))
    errors: list[str] = []
    groups = collect_groups(root)
    for name, current in groups.items():
        recorded = freeze.get("hashes", {}).get(name)
        if recorded is None:
            errors.append(f"group {name}: not recorded in freeze")
        elif recorded.get("digest") != current["digest"]:
            changed = [
                rel for rel in current["files"] if recorded.get("files", {}).get(rel) != current["files"][rel]
            ]
            errors.append(f"group {name}: digest mismatch; changed files: {changed}")
    resolved = images if images is not None else image_digests()
    for provider, recorded in freeze.get("images", {}).items():
        digest = resolved.get(provider)
        if digest is None:
            if require_images:
                errors.append(f"image {provider}: cannot resolve local digest")
        elif recorded.get("digest") != digest:
            errors.append(f"image {provider}: digest mismatch (recorded {recorded.get('digest')}, local {digest})")
    if freeze.get("reader") != FROZEN_READER:
        errors.append("reader settings differ from the frozen pilot selection")
    if freeze.get("schema") != SCHEMA:
        errors.append(f"schema mismatch: {freeze.get('schema')}")
    return errors


def run_dry_run() -> None:
    """$0 offline plumbing dry run on DEV; requires zero manual intervention."""
    result = subprocess.run(DRY_RUN_COMMAND, capture_output=False)
    if result.returncode != 0:
        raise SystemExit(f"DEV dry run failed with exit code {result.returncode}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Freeze and verify the Phase 1 controlled protocol.")
    parser.add_argument(
        "--write",
        action="store_true",
        help="write protocols/v1/config-freeze.json (requires a clean tree)",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="recompute content hashes and compare against the committed freeze",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="verify the freeze, then run the $0 offline DEV plumbing suite",
    )
    parser.add_argument("--out", type=Path, default=FREEZE_PATH)
    args = parser.parse_args()

    if args.dry_run:
        errors = verify_freeze()
        if errors:
            for error in errors:
                print(f"VERIFY FAIL: {error}")
            raise SystemExit(1)
        print("freeze verification passed")
        print("running $0 DEV dry run (offline stub reader)...")
        run_dry_run()
        print("DRY RUN PASSED: zero manual intervention")
        return 0

    if args.verify:
        errors = verify_freeze()
        if errors:
            for error in errors:
                print(f"VERIFY FAIL: {error}")
            raise SystemExit(1)
        print("freeze verification passed")
        return 0

    if args.write:
        freeze = build_freeze()
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(freeze, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"wrote {args.out}")
        print(
            "freeze summary: commit={} prompt_hash={} test_commitment_verified={} "
            "expected_cost_usd={}".format(
                freeze["git"]["commit"][:12],
                freeze["reader_prompt_hash"][:12],
                freeze["test_commitment"]["verified"],
                freeze["cost"]["expected_usd"],
            )
        )
        return 0

    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
