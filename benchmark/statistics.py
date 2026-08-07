"""Deterministic paired statistics: block bootstrap, McNemar, Holm, reliability."""

from __future__ import annotations

import math
import random


def paired_diffs(blocks_a: dict[str, list[float]], blocks_b: dict[str, list[float]]) -> dict[str, list[float]]:
    """Per-block paired differences, aligned by block id (common blocks only)."""
    common = sorted(set(blocks_a) & set(blocks_b))
    diffs: dict[str, list[float]] = {}
    for block in common:
        values_a = blocks_a[block]
        values_b = blocks_b[block]
        diffs[block] = [value_a - value_b for value_a, value_b in zip(values_a, values_b)]
    return diffs


def paired_bootstrap(
    block_diffs: dict[str, list[float]],
    n_resamples: int = 10_000,
    seed: int = 20260805,
    alpha: float = 0.05,
) -> dict:
    """Bootstrap the mean paired difference by resampling whole blocks.

    Blocks are the unit (owner/storyline), so correlated queries inside a
    block stay together. Deterministic for a fixed seed and resample count.
    """
    block_ids = sorted(block_diffs)

    def mean_diff(sample_ids: list[str]) -> float:
        values = [value for block in sample_ids for value in block_diffs[block]]
        return sum(values) / len(values) if values else 0.0

    observed = mean_diff(block_ids)
    rng = random.Random(seed)
    resampled = sorted(
        mean_diff([rng.choice(block_ids) for _ in block_ids]) for _ in range(n_resamples)
    )
    lower_index = int(round(alpha / 2 * n_resamples))
    upper_index = max(lower_index + 1, int(round((1 - alpha / 2) * n_resamples)) - 1)
    return {
        "observed_mean_diff": round(observed, 6),
        "ci_low": round(resampled[lower_index], 6),
        "ci_high": round(resampled[upper_index], 6),
        "resamples": n_resamples,
        "seed": seed,
        "blocks": len(block_ids),
    }


def mcnemar_exact(a_outcomes: list[bool], b_outcomes: list[bool]) -> dict:
    """Exact two-sided McNemar test on discordant pairs."""
    b_wins = sum(1 for a, b in zip(a_outcomes, b_outcomes) if not a and b)
    a_wins = sum(1 for a, b in zip(a_outcomes, b_outcomes) if a and not b)
    discordant = a_wins + b_wins
    if discordant == 0:
        p_value = 1.0
    else:
        k = min(a_wins, b_wins)
        tail = sum(math.comb(discordant, i) for i in range(k + 1)) * (0.5**discordant)
        p_value = min(1.0, 2 * tail)
    return {"a_wins": a_wins, "b_wins": b_wins, "discordant": discordant, "p_value": round(p_value, 6)}


def holm_adjust(p_values: list[float]) -> list[float]:
    """Holm-Bonferroni correction, preserving input order."""
    count = len(p_values)
    order = sorted(range(count), key=lambda index: p_values[index])
    adjusted = [0.0] * count
    running = 0.0
    for rank, index in enumerate(order, 1):
        running = max(running, min(1.0, p_values[index] * (count - rank + 1)))
        adjusted[index] = running
    return [round(value, 6) for value in adjusted]


def pass_at_one(attempt_groups: list[list[bool]]) -> float:
    """Fraction of cases whose first attempt succeeded."""
    if not attempt_groups:
        return 0.0
    return round(sum(1 for group in attempt_groups if group and group[0]) / len(attempt_groups), 4)


def all_success_rate(attempt_groups: list[list[bool]]) -> float:
    """Fraction of cases where every attempt succeeded."""
    if not attempt_groups:
        return 0.0
    return round(sum(1 for group in attempt_groups if group and all(group)) / len(attempt_groups), 4)
