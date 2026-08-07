"""Private deterministic scorer (Stage 4). Never exposes gold to providers.

Reader answers are scored from typed ground truth (exact, set, date, bool,
quantity) with private acceptable aliases. Retrieval is scored with gold
evidence fraction@k and complete-chain@k; forbidden, cross-principal, and
deleted evidence are counted separately. The legacy answer-substring presence
metric is kept only as a deprecated diagnostic.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from benchmark.events import Query, load_ground_truth
from benchmark.model_gateway import ModelResponse
from benchmark.providers import RetrievalResult


def normalize_answer(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9 ]", " ", value)
    return " ".join(value.split())


@dataclass
class QueryScore:
    query_id: str
    kind: str
    expected_abstain: bool
    reader_abstained: bool
    abstain_correct: bool
    retrieved_contains_gold: Optional[bool]
    gold_hits: int
    gold_total: int
    recall_at_1: Optional[bool]
    recall_at_5: Optional[bool]
    recall_at_10: Optional[bool]
    reader_correct: Optional[bool]
    note: str = ""
    gold_recall_at_1: Optional[float] = None
    gold_recall_at_5: Optional[float] = None
    gold_recall_at_10: Optional[float] = None
    chain_complete_at_1: Optional[bool] = None
    chain_complete_at_5: Optional[bool] = None
    chain_complete_at_10: Optional[bool] = None
    evidence_precision: Optional[float] = None
    evidence_recall: Optional[float] = None
    forbidden_evidence: int = 0
    cross_principal_evidence: int = 0
    deleted_evidence: int = 0
    authority_correct: Optional[bool] = None

    def to_dict(self) -> dict:
        return {
            "query_id": self.query_id,
            "kind": self.kind,
            "expected_abstain": self.expected_abstain,
            "reader_abstained": self.reader_abstained,
            "abstain_correct": self.abstain_correct,
            "retrieved_contains_gold": self.retrieved_contains_gold,
            "gold_hits": self.gold_hits,
            "gold_total": self.gold_total,
            "recall@1": self.recall_at_1,
            "recall@5": self.recall_at_5,
            "recall@10": self.recall_at_10,
            "reader_correct": self.reader_correct,
            "gold_evidence_recall@1": self.gold_recall_at_1,
            "gold_evidence_recall@5": self.gold_recall_at_5,
            "gold_evidence_recall@10": self.gold_recall_at_10,
            "chain_complete@1": self.chain_complete_at_1,
            "chain_complete@5": self.chain_complete_at_5,
            "chain_complete@10": self.chain_complete_at_10,
            "evidence_id_precision": self.evidence_precision,
            "evidence_id_recall": self.evidence_recall,
            "forbidden_evidence": self.forbidden_evidence,
            "cross_principal_evidence": self.cross_principal_evidence,
            "deleted_evidence": self.deleted_evidence,
            "authority_correct": self.authority_correct,
            "note": self.note,
        }


@dataclass
class RunScores:
    total: int = 0
    scored: int = 0
    abstain_accuracy: Optional[float] = None
    presence_accuracy: Optional[float] = None
    recall_at_1: Optional[float] = None
    recall_at_5: Optional[float] = None
    recall_at_10: Optional[float] = None
    reader_accuracy: Optional[float] = None
    gold_evidence_recall_at_5: Optional[float] = None
    chain_complete_at_5: Optional[float] = None
    evidence_precision: Optional[float] = None
    evidence_recall: Optional[float] = None
    forbidden_evidence_total: int = 0
    cross_principal_evidence_total: int = 0
    deleted_evidence_total: int = 0
    mutation_warnings: int = 0
    errors: list[str] = field(default_factory=list)
    by_kind: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "scored": self.scored,
            "abstain_accuracy": self.abstain_accuracy,
            "presence_accuracy": self.presence_accuracy,
            "recall@1": self.recall_at_1,
            "recall@5": self.recall_at_5,
            "recall@10": self.recall_at_10,
            "reader_accuracy": self.reader_accuracy,
            "gold_evidence_recall@5": self.gold_evidence_recall_at_5,
            "chain_complete@5": self.chain_complete_at_5,
            "evidence_id_precision": self.evidence_precision,
            "evidence_id_recall": self.evidence_recall,
            "forbidden_evidence_total": self.forbidden_evidence_total,
            "cross_principal_evidence_total": self.cross_principal_evidence_total,
            "deleted_evidence_total": self.deleted_evidence_total,
            "deprecated_metrics": ["presence_accuracy"],
            "mutation_warnings": self.mutation_warnings,
            "errors": self.errors,
            "by_kind": self.by_kind,
        }


class Scorer:
    def __init__(self, gold_path: Path | str | None = None, gold: dict | None = None, version: str = "0.1.0"):
        if gold is not None:
            self.gold = gold
        elif gold_path is not None:
            self.gold = load_ground_truth(gold_path)
        else:
            raise ValueError("Scorer requires gold_path or gold")
        self.version = version
        self.errors: list[str] = []

    def score_query(
        self,
        query: Query,
        retrieval: RetrievalResult,
        response: ModelResponse,
        deleted_event_ids: frozenset[str] = frozenset(),
    ) -> QueryScore:
        gold = self.gold.get(query.query_id)
        if gold is None:
            self.errors.append(f"no ground truth row for {query.query_id}")
            return QueryScore(
                query.query_id,
                query.kind,
                False,
                bool(response.structured.get("abstain", False)),
                False,
                None,
                0,
                0,
                None,
                None,
                None,
                None,
                note="missing ground truth",
            )
        return self._score(gold, query, retrieval, response, deleted_event_ids)

    def _score(
        self,
        gold,
        query: Query,
        retrieval: RetrievalResult,
        response: ModelResponse,
        deleted_event_ids: frozenset[str],
    ) -> QueryScore:
        expected_abstain = gold.abstain
        reader_abstained = bool(response.structured.get("abstain", False))
        abstain_correct = expected_abstain == reader_abstained

        gold_ids = set(gold.gold_event_ids)
        item_ids = [it.item_id for it in retrieval.items]

        presence: Optional[bool] = None
        if gold.answer is not None:
            norm = normalize_answer(gold.answer)
            presence = any(norm in normalize_answer(it.text) for it in retrieval.items)

        gold_hits = sum(1 for iid in item_ids if iid in gold_ids)
        gold_total = len(gold.gold_event_ids)

        recall_at_1 = bool(gold_ids & set(item_ids[:1])) if gold_total else None
        recall_at_5 = bool(gold_ids & set(item_ids[:5])) if gold_total else None
        recall_at_10 = bool(gold_ids & set(item_ids[:10])) if gold_total else None
        def gold_fraction_at(k: int) -> Optional[float]:
            if not gold_total:
                return None
            return round(len(gold_ids & set(item_ids[:k])) / gold_total, 4)

        def chain_complete_at(k: int) -> Optional[bool]:
            if not gold_total:
                return None
            return gold_ids.issubset(set(item_ids[:k]))

        reader_correct: Optional[bool] = None
        if expected_abstain:
            reader_correct = reader_abstained
        elif reader_abstained:
            reader_correct = False
        else:
            answer = response.structured.get("answer")
            reader_correct = (
                answer is not None and _typed_answer_matches(gold, str(answer))
            )

        cited = set(response.structured.get("evidence_ids") or [])
        evidence_precision = round(len(cited & gold_ids) / len(cited), 4) if cited else 0.0
        evidence_recall = round(len(cited & gold_ids) / len(gold_ids), 4) if gold_ids else None
        forbidden_evidence = sum(
            1 for item in retrieval.items if item.metadata.get("kind") == "poison_attempt"
        )
        cross_principal_evidence = sum(
            1
            for item in retrieval.items
            if item.metadata.get("principal") not in (None, query.principal)
        )
        deleted_evidence = sum(1 for item in retrieval.items if item.item_id in deleted_event_ids)
        authority_correct: Optional[bool] = None
        if query.kind == "authority_conflict" and not expected_abstain:
            authority_correct = bool(cited) and cited <= gold_ids and forbidden_evidence == 0

        result = QueryScore(
            query.query_id,
            query.kind,
            expected_abstain,
            reader_abstained,
            abstain_correct,
            presence,
            gold_hits,
            gold_total,
            recall_at_1,
            recall_at_5,
            recall_at_10,
            reader_correct,
        )
        result.gold_recall_at_1 = gold_fraction_at(1)
        result.gold_recall_at_5 = gold_fraction_at(5)
        result.gold_recall_at_10 = gold_fraction_at(10)
        result.chain_complete_at_1 = chain_complete_at(1)
        result.chain_complete_at_5 = chain_complete_at(5)
        result.chain_complete_at_10 = chain_complete_at(10)
        result.evidence_precision = evidence_precision
        result.evidence_recall = evidence_recall
        result.forbidden_evidence = forbidden_evidence
        result.cross_principal_evidence = cross_principal_evidence
        result.deleted_evidence = deleted_evidence
        result.authority_correct = authority_correct
        return result


def _accuracy(values: list[bool]) -> Optional[float]:
    if not values:
        return None
    return round(sum(1 for v in values if v) / len(values), 4)


def _mean(values: list[float]) -> Optional[float]:
    if not values:
        return None
    return round(sum(values) / len(values), 4)


def aggregate_scores(query_scores: list[QueryScore], errors: list[str] | None = None) -> RunScores:
    agg = RunScores(total=len(query_scores), errors=list(errors or []))
    scored = [qs for qs in query_scores if qs.note != "missing ground truth"]
    agg.scored = len(scored)

    abstain_values = [qs.abstain_correct for qs in scored]
    presence_values = [qs.retrieved_contains_gold for qs in scored if qs.retrieved_contains_gold is not None]
    recall_1 = [qs.recall_at_1 for qs in scored if qs.recall_at_1 is not None]
    recall_5 = [qs.recall_at_5 for qs in scored if qs.recall_at_5 is not None]
    recall_10 = [qs.recall_at_10 for qs in scored if qs.recall_at_10 is not None]
    reader_values = [qs.reader_correct for qs in scored if qs.reader_correct is not None]

    agg.abstain_accuracy = _accuracy(abstain_values)
    agg.presence_accuracy = _accuracy(presence_values)
    agg.recall_at_1 = _accuracy(recall_1)
    agg.recall_at_5 = _accuracy(recall_5)
    agg.recall_at_10 = _accuracy(recall_10)
    agg.reader_accuracy = _accuracy(reader_values)
    agg.gold_evidence_recall_at_5 = _mean(
        [qs.gold_recall_at_5 for qs in scored if qs.gold_recall_at_5 is not None]
    )
    agg.chain_complete_at_5 = _accuracy(
        [qs.chain_complete_at_5 for qs in scored if qs.chain_complete_at_5 is not None]
    )
    agg.evidence_precision = _mean(
        [qs.evidence_precision for qs in scored if qs.evidence_precision is not None]
    )
    agg.evidence_recall = _mean(
        [qs.evidence_recall for qs in scored if qs.evidence_recall is not None]
    )
    agg.forbidden_evidence_total = sum(qs.forbidden_evidence for qs in scored)
    agg.cross_principal_evidence_total = sum(qs.cross_principal_evidence for qs in scored)
    agg.deleted_evidence_total = sum(qs.deleted_evidence for qs in scored)

    by_kind: dict = {}
    for qs in scored:
        bucket = by_kind.setdefault(qs.kind, [])
        bucket.append(qs)
    for kind, items in by_kind.items():
        by_kind[kind] = {
            "total": len(items),
            "abstain_accuracy": _accuracy([qs.abstain_correct for qs in items]),
            "presence_accuracy": _accuracy(
                [qs.retrieved_contains_gold for qs in items if qs.retrieved_contains_gold is not None]
            ),
            "recall@5": _accuracy([qs.recall_at_5 for qs in items if qs.recall_at_5 is not None]),
            "reader_accuracy": _accuracy([qs.reader_correct for qs in items if qs.reader_correct is not None]),
            "gold_evidence_recall@5": _mean(
                [qs.gold_recall_at_5 for qs in items if qs.gold_recall_at_5 is not None]
            ),
            "chain_complete@5": _accuracy(
                [qs.chain_complete_at_5 for qs in items if qs.chain_complete_at_5 is not None]
            ),
            "evidence_id_precision": _mean(
                [qs.evidence_precision for qs in items if qs.evidence_precision is not None]
            ),
            "authority_correct": _accuracy(
                [qs.authority_correct for qs in items if qs.authority_correct is not None]
            ),
        }
    agg.by_kind = by_kind
    return agg


ANSWER_TYPES = ("exact", "set", "date", "bool", "quantity")


def _split_set(value: str) -> set[str]:
    parts = re.split(r",|;|\||/|\band\b", value.lower())
    return {normalize_answer(part) for part in parts if part.strip()}


def _parse_bool(value: str) -> Optional[bool]:
    norm = normalize_answer(value)
    if norm in {"yes", "true", "1", "y"}:
        return True
    if norm in {"no", "false", "0", "n"}:
        return False
    return None


def _parse_quantity(value: str) -> Optional[float]:
    cleaned = re.sub(r"[^0-9.\-]", "", value)
    try:
        return float(cleaned)
    except ValueError:
        return None


def _typed_answer_matches(gold, answer: str) -> bool:
    if gold.answer_type == "set":
        expected = _split_set(gold.answer)
        candidates = [expected] + [_split_set(alias) for alias in gold.acceptable_answers]
        return any(_split_set(answer) == candidate for candidate in candidates)
    if gold.answer_type == "bool":
        expected = _parse_bool(gold.answer)
        return expected is not None and _parse_bool(answer) == expected
    if gold.answer_type == "quantity":
        expected = _parse_quantity(gold.answer)
        actual = _parse_quantity(answer)
        if expected is None or actual is None:
            return False
        return abs(expected - actual) <= max(0.01, abs(expected) * 0.005)
    norm = normalize_answer(answer)
    return norm == normalize_answer(gold.answer or "") or any(
        norm == normalize_answer(alias) for alias in gold.acceptable_answers
    )
