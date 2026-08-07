"""Fail-closed Phase 0 orchestrator with checkpoint-specific replay."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

from benchmark import manifests
from benchmark.clock import BenchmarkClock
from benchmark.config import Settings
from benchmark.events import Query, corpus_digest, load_events, load_ground_truth, load_queries
from benchmark.lifecycle import LifecycleError, run_ingestion
from benchmark.model_gateway import BaseGateway
from benchmark.providers import MemoryProvider
from benchmark.scorer import RunScores, Scorer, aggregate_scores
from benchmark.schema import SchemaError
from benchmark.snapshots import check_no_mutation
from benchmark.token_budget import format_evidence
from benchmark.validation import validate_corpus


class RunInvariantError(RuntimeError):
    """A state-isolation invariant failed; scores from the run are invalid."""


@dataclass
class RunConfig:
    run_id: str
    provider: MemoryProvider
    gateway: BaseGateway
    settings: Settings
    scorer: Scorer
    preflight_results: list = field(default_factory=list)
    control: bool = False
    notes: str = ""
    incremental: bool = False  # native track: no per-checkpoint reset, delta ingestion


@dataclass
class RunOutcome:
    run_id: str
    run_dir: Path
    manifest_path: Path
    scores: RunScores
    query_scores: list
    preflight_ok: bool
    mutation_warnings: int
    traces_path: Path
    scores_path: Path
    gateway_log_path: Path
    status: str
    status_reason: str = ""


def run_baseline(cfg: RunConfig, queries_override: list[Query] | None = None) -> RunOutcome:
    run_dir = cfg.settings.run_root / cfg.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    traces_path = run_dir / "retrieval_trace.jsonl"
    scores_path = run_dir / "scores.json"
    log = _RunLog(run_dir / "run.log")
    log.write(f"run {cfg.run_id} start; provider={cfg.provider.name}; gateway_mode={cfg.gateway.mode}")
    schema_failure_reason = ""

    try:
        events = load_events(cfg.settings.corpus_dir / "events.jsonl")
        if queries_override is None:
            queries = sorted(load_queries(cfg.settings.corpus_dir / "queries.jsonl"), key=lambda q: (q.as_of, q.query_id))
        else:
            queries = sorted(queries_override, key=lambda q: (q.as_of, q.query_id))
        gold = load_ground_truth(cfg.settings.gold_path)
    except SchemaError as exc:
        events, queries, gold = [], [], {}
        schema_failure_reason = str(exc)
        log.write(f"DATASET SCHEMA FAILURE - aborting before ingestion: {schema_failure_reason}")

    validation_gold = gold
    if queries_override is not None:
        validation_gold = {
            query_id: gold[query_id]
            for query_id in {query.query_id for query in queries}
            if query_id in gold
        }
    validation = validate_corpus(events, queries, validation_gold)
    isolation_failed = [r for r in cfg.preflight_results if r.required and r.applicable and not r.passed]
    preflight_ok = not isolation_failed
    status = "created"
    status_reason = ""
    traces: list[dict] = []
    query_scores: list = []
    scores = RunScores()
    provider_stats: dict = {}

    try:
        if schema_failure_reason:
            status = "invalid_dataset"
            status_reason = schema_failure_reason
        elif not validation.passed:
            status = "invalid_dataset"
            status_reason = "; ".join(validation.errors)
            log.write(f"DATASET FAILURE - aborting before ingestion: {status_reason}")
        elif not preflight_ok:
            status = "aborted_preflight"
            status_reason = "; ".join(f"{r.check}: {r.details}" for r in isolation_failed)
            log.write(f"PREFLIGHT FAILURE - aborting before ingestion: {status_reason}")
        else:
            by_checkpoint: dict[str, list[Query]] = {}
            for query in queries:
                by_checkpoint.setdefault(query.as_of, []).append(query)

            previous_as_of: str | None = None
            for as_of, checkpoint_queries in sorted(by_checkpoint.items()):
                checkpoint_clock = BenchmarkClock(as_of)
                ingest = run_ingestion(
                    cfg.provider,
                    events,
                    checkpoint_clock,
                    incremental=cfg.incremental,
                    since=previous_as_of,
                )
                previous_as_of = as_of
                baseline = cfg.provider.snapshot()
                baseline.taken_at = checkpoint_clock.now()
                checkpoint = {
                    "as_of": as_of,
                    "eligible_event_ids": list(ingest.eligible_event_ids),
                    "lifecycle_actions": list(ingest.lifecycle_actions),
                    "ingested": ingest.ingested,
                    "state_hash": baseline.state_hash,
                }
                log.write(
                    f"checkpoint {as_of}: eligible={ingest.eligible} ingested={ingest.ingested} "
                    f"actions={len(ingest.lifecycle_actions)} state={baseline.state_hash}"
                )
                for query in sorted(checkpoint_queries, key=lambda q: q.query_id):
                    trace = _run_query(cfg, query, baseline, checkpoint, checkpoint_clock, log)
                    traces.append(trace["row"])
                    query_scores.append(trace["score_obj"])

            scores = aggregate_scores(query_scores, errors=list(cfg.scorer.errors))
            if not cfg.gateway.describe().get("semantic_reader_validated", False):
                scores.abstain_accuracy = None
                scores.reader_accuracy = None
            status = (
                "completed_publishable"
                if _publication_eligible(cfg.gateway, cfg.preflight_results)
                else "completed_plumbing"
            )
            manifests.write_traces(run_dir, traces)
            manifests.write_scores(run_dir, scores.to_dict())
            log.write(f"run complete: status={status} queries={len(query_scores)}")
    except (RunInvariantError, LifecycleError) as exc:
        status = "invalid_invariant"
        status_reason = str(exc)
        log.write(f"RUN INVALIDATED: {status_reason}")
    finally:
        try:
            provider_stats = cfg.provider.stats()
        finally:
            cfg.provider.cleanup()

    reader = cfg.gateway.describe()
    response_models = sorted(
        {row["reader"]["response_model_id"] for row in traces if row["reader"].get("response_model_id")}
    )
    if response_models:
        reader["returned_models"] = response_models
        if len(response_models) == 1:
            reader["actual_model"] = response_models[0]

    publication_reasons = _publication_reasons(status, cfg.gateway, cfg.preflight_results)
    preflight_dict = {"passed": preflight_ok, "results": [r.to_dict() for r in cfg.preflight_results]}
    manifest = manifests.build_manifest(
        run_id=cfg.run_id,
        track=cfg.settings.track,
        settings=cfg.settings,
        provider_name=cfg.provider.name,
        provider_version=cfg.provider.version,
        provider_capabilities=cfg.provider.capabilities.to_dict(),
        control=cfg.control,
        corpus_digest_value=corpus_digest(
            cfg.settings.corpus_dir / "events.jsonl",
            cfg.settings.corpus_dir / "queries.jsonl",
            cfg.settings.gold_path,
        ),
        corpus_split="dev",
        prompt_digest_value=manifests.prompt_digest(cfg.settings.prompt_path, cfg.settings.prompt_version),
        bench_time=cfg.settings.clock_start,
        preflight=preflight_dict,
        scores=scores.to_dict() if status.startswith("completed_") else None,
        scorer_version=cfg.scorer.version,
        provider_stats=provider_stats,
        status=status,
        status_reason=status_reason,
        reader=reader,
        publication={"eligible": not publication_reasons, "reasons": publication_reasons},
        dataset_validation=validation.to_dict(),
        notes=cfg.notes,
    )
    manifest_path = manifests.write_manifest(run_dir, manifest)
    return RunOutcome(
        run_id=cfg.run_id,
        run_dir=run_dir,
        manifest_path=manifest_path,
        scores=scores,
        query_scores=query_scores,
        preflight_ok=preflight_ok,
        mutation_warnings=0,
        traces_path=traces_path,
        scores_path=scores_path,
        gateway_log_path=run_dir / "gateway.log",
        status=status,
        status_reason=status_reason,
    )


def _run_query(cfg: RunConfig, query: Query, baseline, checkpoint: dict, clock: BenchmarkClock, log: "_RunLog") -> dict:
    # Execution optimization (user-directed, 2026-08-06): queries at the same
    # checkpoint share the verified checkpoint state instead of re-ingesting
    # per query. The isolation guarantee is unchanged: the state must still
    # equal the checkpoint baseline before retrieval, and any mutation caused
    # by retrieval invalidates the run (both checks below). Contract-passing
    # providers are read-only, so per-query restore was semantically a no-op
    # that cost O(events) re-ingestion for every query.
    before = cfg.provider.snapshot()
    before.taken_at = clock.now()
    if before.state_hash != baseline.state_hash:
        raise RunInvariantError(
            f"{query.query_id}: state hash mismatch with checkpoint baseline; "
            f"expected {baseline.state_hash}, got {before.state_hash}"
        )

    t0 = time.perf_counter()
    retrieval = cfg.provider.retrieve(query)
    retrieval.latency_ms = (time.perf_counter() - t0) * 1000.0
    after = cfg.provider.snapshot()
    after.taken_at = clock.now()
    mutation = check_no_mutation(before, after)
    retrieval.mutated = not mutation.passed
    if not mutation.passed:
        raise RunInvariantError(f"{query.query_id}: provider state mutated during read-only retrieval")

    bundle = format_evidence(retrieval.items, cfg.settings.token_budget)
    included_ids = set(bundle.item_ids)
    reader_evidence = [item for item in retrieval.items if item.item_id in included_ids]
    response = cfg.gateway.generate(query, reader_evidence, cfg.settings.prompt_version)
    deleted_event_ids = frozenset(
        action.split(":", 1)[1]
        for action in checkpoint["lifecycle_actions"]
        if action.startswith("delete:")
    )
    score = cfg.scorer.score_query(query, retrieval, response, deleted_event_ids=deleted_event_ids)

    log.write(
        f"query {query.query_id} ({query.kind}): retrieved={len(retrieval.items)} "
        f"sent={len(reader_evidence)} tokens={bundle.tokens} truncated={bundle.truncated}"
    )
    row = {
        "query_id": query.query_id,
        "question": query.question,
        "principal": query.principal,
        "subject": query.subject,
        "scope": query.scope,
        "as_of": query.as_of,
        "kind": query.kind,
        "checkpoint": checkpoint,
        "restore_ok": True,
        "retrieval": {
            "item_ids": [item.item_id for item in retrieval.items],
            "scores": [item.score for item in retrieval.items],
            "latency_ms": round(retrieval.latency_ms, 3),
            "raw": retrieval.raw,
        },
        "evidence": {
            "tokens": bundle.tokens,
            "token_estimator": bundle.estimator,
            "truncated": bundle.truncated,
            "omitted_items": bundle.omitted_items,
            "item_ids": list(bundle.item_ids),
        },
        "reader": {
            "mode": response.mode,
            "model_id": response.model_id,
            "response_model_id": response.response_model_id,
            "request_id": response.request_id,
            "structured": response.structured,
            "request_tokens": response.request_tokens,
            "response_tokens": response.response_tokens,
            "retries": response.retries,
            "latency_ms": round(response.latency_ms, 3),
            "prompt_hash": response.prompt_hash,
            "usage": response.usage,
            "attestation": response.attestation,
        },
        "score": score.to_dict(),
        "mutation_check": {
            "passed": True,
            "before": before.state_hash,
            "after": after.state_hash,
            "details": mutation.details,
        },
    }
    return {"row": row, "score_obj": score}


def _publication_eligible(gateway: BaseGateway, results: list) -> bool:
    return not _publication_reasons("completed_publishable", gateway, results)


def _publication_reasons(status: str, gateway: BaseGateway, results: list) -> list[str]:
    reasons: list[str] = []
    if not status.startswith("completed_"):
        reasons.append(f"run status is {status}")
    if not gateway.describe().get("semantic_reader_validated", False):
        reasons.append("offline plumbing reader is not a validated semantic reader")
    required_not_applicable = [result.check for result in results if result.required and not result.applicable]
    if required_not_applicable:
        reasons.append(f"required runtime controls not applicable: {', '.join(sorted(required_not_applicable))}")
    failed = [result.check for result in results if result.required and result.applicable and not result.passed]
    if failed:
        reasons.append(f"required preflight failed: {', '.join(sorted(failed))}")
    return reasons


class _RunLog:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, line: str) -> None:
        with open(self.path, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")
