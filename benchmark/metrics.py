"""Declared metric families for multiple-comparison control and reporting."""

from __future__ import annotations

METRIC_FAMILIES: dict[str, list[str]] = {
    "retrieval": [
        "gold_evidence_recall@5",
        "chain_complete@5",
        "evidence_id_precision",
        "evidence_id_recall",
        "forbidden_evidence_total",
        "cross_principal_evidence_total",
        "deleted_evidence_total",
    ],
    "reader": [
        "reader_accuracy",
        "abstain_accuracy",
        "authority_correct",
    ],
    "reliability": [
        "pass_at_1",
        "all_success_rate",
    ],
    "operational": [
        "mean_latency_ms",
        "mean_tokens",
    ],
}


def metric_family(metric: str) -> str | None:
    for family, members in METRIC_FAMILIES.items():
        if metric in members:
            return family
    return None


def families() -> dict[str, list[str]]:
    return {family: list(members) for family, members in METRIC_FAMILIES.items()}
