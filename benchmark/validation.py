"""Deterministic corpus integrity checks run before benchmark scoring.

Schema-level validation of every on-disk record happens in the dataset loaders
(benchmark/events.py) using the versioned schemas in schemas/. This module
performs the semantic cross-checks that schemas cannot express: referential
integrity, temporal validity, lifecycle targeting, and split safety.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from benchmark.events import Event, GroundTruth, Query


@dataclass(frozen=True)
class ValidationResult:
    passed: bool
    errors: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict:
        return {"passed": self.passed, "errors": list(self.errors), "warnings": list(self.warnings)}


def validate_corpus(
    events: list[Event],
    queries: list[Query],
    gold: dict[str, GroundTruth] | list[GroundTruth],
) -> ValidationResult:
    """Check referential, temporal, lifecycle, and split-safe invariants."""
    errors: list[str] = []
    warnings: list[str] = []
    gold_map = gold if isinstance(gold, dict) else {row.query_id: row for row in gold}

    event_ids = [event.event_id for event in events]
    if len(event_ids) != len(set(event_ids)):
        errors.append("duplicate event_id")
    query_ids = [query.query_id for query in queries]
    if len(query_ids) != len(set(query_ids)):
        errors.append("duplicate query_id")

    by_id = {event.event_id: event for event in events}
    for event in events:
        if event.operation not in {"upsert", "delete"}:
            errors.append(f"{event.event_id}: unsupported operation {event.operation!r}")
        if not event.subject:
            errors.append(f"{event.event_id}: missing subject")
        if event.valid_from and event.valid_to and event.valid_from >= event.valid_to:
            errors.append(f"{event.event_id}: valid_from must be before valid_to")
        if event.operation == "delete":
            target = by_id.get(event.target_event_id or "")
            if target is None:
                errors.append(f"{event.event_id}: delete target missing")
            elif target.available_at >= event.available_at:
                errors.append(f"{event.event_id}: delete target is not earlier than request")
            elif target.principal != event.principal:
                errors.append(f"{event.event_id}: delete target crosses principal boundary")
        elif event.target_event_id:
            errors.append(f"{event.event_id}: upsert event cannot have target_event_id")

    if set(query_ids) != set(gold_map):
        missing = sorted(set(query_ids) - set(gold_map))
        extra = sorted(set(gold_map) - set(query_ids))
        if missing:
            errors.append(f"queries missing gold: {missing}")
        if extra:
            errors.append(f"gold without query: {extra}")

    for query in queries:
        row = gold_map.get(query.query_id)
        if row is None:
            continue
        if not query.subject:
            errors.append(f"{query.query_id}: missing subject")
        if row.abstain:
            if row.answer is not None or row.gold_event_ids:
                errors.append(f"{query.query_id}: abstention row contains answer or gold evidence")
        elif row.answer is None or not row.gold_event_ids:
            errors.append(f"{query.query_id}: answerable row lacks answer or gold evidence")
        if query.kind == "multi_hop" and len(row.gold_event_ids) < 2:
            errors.append(f"{query.query_id}: multi-hop gold lacks a complete evidence chain")
        for event_id in row.gold_event_ids:
            event = by_id.get(event_id)
            if event is None:
                errors.append(f"{query.query_id}: unknown gold event {event_id}")
                continue
            if event.available_at > query.as_of:
                errors.append(f"{query.query_id}: gold event {event_id} is future information")
            if event.operation != "upsert":
                errors.append(f"{query.query_id}: lifecycle command {event_id} used as answer evidence")
            if event.principal != query.principal:
                errors.append(f"{query.query_id}: gold event {event_id} is outside requester principal")

    return ValidationResult(passed=not errors, errors=tuple(errors), warnings=tuple(warnings))


def validate_dataset_files(
    events_path,
    queries_path,
    gold_path,
) -> ValidationResult:
    """Load (schema-validated) dataset files and run the semantic gate."""
    from benchmark.events import load_events, load_ground_truth, load_queries

    events = load_events(events_path)
    queries = load_queries(queries_path)
    gold = load_ground_truth(gold_path)
    return validate_corpus(events, queries, gold)


STRUCTURAL_ANSWERS = {"user"}  # provenance source labels, not factual content


def validate_split_isolation(
    dev_events: list[Event],
    dev_queries: list[Query],
    dev_gold: dict[str, GroundTruth],
    test_events: list[Event],
    test_queries: list[Query],
    test_gold: dict[str, GroundTruth],
) -> ValidationResult:
    """DEV/TEST split hygiene: no shared identifiers, questions, or answers."""
    errors: list[str] = []
    warnings: list[str] = []

    dev_event_ids = {event.event_id for event in dev_events}
    test_event_ids = {event.event_id for event in test_events}
    shared_events = dev_event_ids & test_event_ids
    if shared_events:
        errors.append(f"shared event ids across splits: {sorted(shared_events)[:5]}")

    dev_query_ids = {query.query_id for query in dev_queries}
    test_query_ids = {query.query_id for query in test_queries}
    shared_queries = dev_query_ids & test_query_ids
    if shared_queries:
        errors.append(f"shared query ids across splits: {sorted(shared_queries)[:5]}")

    dev_questions = {query.question for query in dev_queries}
    test_questions = {query.question for query in test_queries}
    shared_questions = dev_questions & test_questions
    if shared_questions:
        warnings.append(f"identical question templates across splits: {len(shared_questions)}")

    dev_pairs = {
        (query.question, dev_gold[query.query_id].answer)
        for query in dev_queries
        if query.query_id in dev_gold and dev_gold[query.query_id].answer
    }
    test_pairs = {
        (query.question, test_gold[query.query_id].answer)
        for query in test_queries
        if query.query_id in test_gold and test_gold[query.query_id].answer
    }
    shared_pairs = dev_pairs & test_pairs
    if shared_pairs:
        errors.append(f"question-answer pairs shared across splits: {sorted(shared_pairs, key=str)[:5]}")

    dev_answers = {row.answer for row in dev_gold.values() if row.answer}
    test_answers = {row.answer for row in test_gold.values() if row.answer}
    leaked_answers = (dev_answers & test_answers) - STRUCTURAL_ANSWERS
    if leaked_answers:
        errors.append(f"answer values shared across splits: {sorted(leaked_answers)[:5]}")

    def four_grams(questions) -> set[str]:
        grams: set[str] = set()
        for question in questions:
            tokens = question.lower().split()
            grams.update(" ".join(tokens[index : index + 4]) for index in range(len(tokens) - 3))
        return grams

    shared_grams = four_grams(dev_questions) & four_grams(test_questions)
    if shared_grams:
        warnings.append(f"shared 4-gram question fragments across splits: {len(shared_grams)}")

    return ValidationResult(passed=not errors, errors=tuple(errors), warnings=tuple(warnings))
