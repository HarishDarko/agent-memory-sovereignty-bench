# Key Result Tables — Capability Attribution Ablation v1

All values are reader-correct rates over attempts (three replicates per cell)
unless noted. Full per-condition detail is in
`runs/followups/capability-attribution-v1/test/analysis/analysis.json`.

## Authority (2 by 2 grid)

| Provider | M0P0 | M0P1 | M1P0 | M1P1 | Delta | Material |
|---|---:|---:|---:|---:|---:|---|
| GBrain | 0.667 | 1.000 | 1.000 | 1.000 | +0.333 | no (p=1.0) |
| Mem0 | 0.833 | 1.000 | 1.000 | 1.000 | +0.167 | no (p=1.0) |
| Hindsight | 0.889 | 1.000 | 1.000 | 1.000 | +0.111 | no (p=1.0) |

Wrong-authority selections: 5 / 1 / 2 in M0P0; zero in every assisted cell.

## Provenance (2 by 2 grid)

| Provider | M0P0 | M0P1 | M1P0 | M1P1 | Delta | Material |
|---|---:|---:|---:|---:|---:|---|
| GBrain | 0.000 | 0.000 | 1.000 | 0.889 | +0.889 | no (underpowered) |
| Mem0 | 0.000 | 0.000 | 1.000 | 1.000 | +1.000 | no (underpowered) |
| Hindsight | 0.000 | 0.000 | 1.000 | 1.000 | +1.000 | no (underpowered) |

Prompt alone: 0.000 for all providers. Metadata alone: 1.000 (GBrain 1.000).

## Temporal (paired)

| Provider | C0-native | C1-assisted | Delta | Holm p | CI (95%) | Material |
|---|---:|---:|---:|---:|---:|---|
| GBrain | 0.537 | 1.000 | +0.463 | 3.1e-05 | 0.426 to 0.491 | YES |
| Mem0 | 0.528 | 1.000 | +0.472 | 3.0e-05 | 0.435 to 0.500 | YES |

Future evidence: 558 to 0 (GBrain), 618 to 0 (Mem0). Future answer leakage:
45 to 0, 49 to 0.

## Scope (paired)

| Provider | D0-native | D1-assisted | Delta | Cross-principal | Unauthorized | Holm p |
|---|---:|---:|---:|---:|---:|---|
| GBrain | 0.333 | 1.000 | +0.667 | 306 to 0 | 18 to 0 | 0.094 |
| Mem0 | 1.000 | 1.000 | 0.000 | 0 to 0 | 0 to 0 | 1.000 |
| Hindsight | 0.333 | 1.000 | +0.667 | 483 to 0 | 18 to 0 | 0.094 |

The correctness delta is not material by the strict rule, but the
preregistered security-count exception applies to the leakage transition
(nonzero to zero).

Interpretation caveat: the assisted scope condition also applied temporal
eligibility filtering; the delta combines scope and temporal interventions,
while the raw cross-principal exposure counts are directly observed. See
`docs/scientific-audit.md`.

## Deletion (descriptive)

Raw deleted evidence after product-native deletion: 0 for GBrain, Mem0, and
Hindsight across all six deletion queries each.

## Retrieval observations

| Property | Queries | Raw items | Assisted items | Changed by assistance |
|---|---:|---:|---:|---:|
| Authority | 18 | 714 | 638 | 18 |
| Provenance | 9 | 357 | 321 | 9 |
| Temporal | 72 | 1353 | 960 | 72 |
| Scope | 27 | 978 | 9 | 21 |

Mutation failures: 0.

## Data quality

918 attempt rows, 144 retrieval rows, 18 deletion rows, 8 reader errors
(retained in denominators), all manifest hashes verified, dataset commitment
hashes matched for every pack.

## Capability Attribution Matrix

Labels: PRIMARY, CONTRIBUTES, VERIFIES, NOT INVOLVED, NOT OBSERVABLE,
UNSUPPORTED.

| Capability | Product | Adapter | Runner | Reader | Scorer |
|---|---|---|---|---|---|
| Factual retrieval | PRIMARY | CONTRIBUTES | VERIFIES | NOT INVOLVED | NOT INVOLVED |
| Authority representation | CONTRIBUTES | PRIMARY | NOT INVOLVED | NOT INVOLVED | VERIFIES |
| Authority reasoning | NOT INVOLVED | CONTRIBUTES | NOT INVOLVED | PRIMARY | VERIFIES |
| Provenance representation | CONTRIBUTES | PRIMARY | NOT INVOLVED | NOT INVOLVED | VERIFIES |
| Provenance reasoning | NOT INVOLVED | CONTRIBUTES | NOT INVOLVED | PRIMARY | VERIFIES |
| Temporal filtering | CONTRIBUTES | CONTRIBUTES | PRIMARY | NOT INVOLVED | VERIFIES |
| Current-state resolution | CONTRIBUTES | CONTRIBUTES | PRIMARY | CONTRIBUTES | VERIFIES |
| Principal isolation | CONTRIBUTES | CONTRIBUTES | PRIMARY | NOT INVOLVED | VERIFIES |
| Scope filtering | CONTRIBUTES | CONTRIBUTES | PRIMARY | NOT INVOLVED | VERIFIES |
| Deletion operation | PRIMARY | CONTRIBUTES | VERIFIES | NOT INVOLVED | NOT INVOLVED |
| Deletion verification | CONTRIBUTES | NOT INVOLVED | PRIMARY | NOT INVOLVED | NOT INVOLVED |
| Read-only guarantee | CONTRIBUTES | NOT INVOLVED | PRIMARY | NOT INVOLVED | NOT INVOLVED |
| Future filtering | CONTRIBUTES | CONTRIBUTES | PRIMARY | NOT INVOLVED | VERIFIES |
| Correctness judgment | NOT INVOLVED | NOT INVOLVED | VERIFIES | CONTRIBUTES | PRIMARY |

Principal isolation: Mem0 PRIMARY (native `user_id`); GBrain and Hindsight
UNSUPPORTED natively, runner-supplied here. Scope: benchmark runner supplies
scope equality for all three.

## Cost

| Provider | Requests | Input tokens | Output tokens | Cost USD |
|---|---:|---:|---:|---:|
| GBrain (incl. 2 abandoned) | 385 | 609,000 | 331,715 | 0.178140 |
| Mem0 | 381 | 676,703 | 298,234 | 0.178244 |
| Hindsight | 162 | 328,656 | 85,810 | 0.070039 |
| Total | 928 | 1,614,359 | 715,759 | 0.426423 |

Model identity observed: `deepseek-v4-flash` on every call.
