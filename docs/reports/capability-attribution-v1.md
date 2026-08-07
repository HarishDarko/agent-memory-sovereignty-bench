# Capability Attribution Ablation v1

**Date:** 2026-08-07
**Preregistration commit:** `47493191daa11cc02549f997742dd5b82e5214c8`
**Implementation freeze commit:** `d97300b29697ce34c52a6ced163c7a95922363ec`
**Deviation record:** `protocols/capability-attribution-v1/deviations.md`
**Run code commit (all nine TEST packs):** `97f1f81974e0d32f417fd959db1c8bc946c0fcae`
**Analysis artifacts:** `runs/followups/capability-attribution-v1/test/analysis/`

## 1. Executive summary

This experiment asks how much measured memory-governance correctness comes
from the memory product itself versus semantic or filtering assistance
supplied by the benchmark adapter, runner, reader prompt, or scorer.

Three results are material or qualitatively decisive:

1. Temporal correctness is essentially benchmark-supplied. With native
   retrieval, GBrain scored 0.537 and Mem0 0.528 on temporal questions, and
   the reader cited future evidence 45 and 49 times. After the benchmark
   applied `available_at <= as_of` filtering to the identical raw evidence,
   both providers scored 1.000 with zero future leakage. The paired effect
   clears every preregistered gate (Holm-adjusted p 3.1e-05 and 3.0e-05,
   bootstrap intervals excluding zero, 16 and 17 discordant pairs, deltas
   0.463 and 0.472).
2. Principal isolation is benchmark-supplied for GBrain and Hindsight. Their
   native retrieval returned 306 and 483 cross-principal evidence items and
   produced 18 unauthorized answers each; benchmark post-filtering reduced
   both to zero. Mem0 needed no assistance because its native `user_id`
   search filter already isolates principals. The correctness delta fails the
   strict significance gate (Holm p 0.094), but the preregistered
   security-count exception applies to the zero-to-nonzero leakage transition.
3. Provenance source identification depends entirely on benchmark metadata.
   With text-only evidence, all three providers scored 0.000; with
   benchmark-supplied source metadata, 0.889 to 1.000. The governance prompt
   alone changed nothing (0.000 to 0.000). The effect is stark and consistent
   across providers but rests on three queries per provider and is declared
   underpowered by the preregistration.

Authority assistance also moves scores (0.667 to 1.000 for GBrain, 0.833 to
1.000 for Mem0, 0.889 to 1.000 for Hindsight), with metadata and instruction
contributing roughly equally and interacting negatively, but only two to six
queries per provider and ceiling effects prevent statistical resolution.

Deletion is the one governance property the products supply natively: after
product-native deletion, zero deleted evidence is retrievable by any provider
without any benchmark post-filtering.

The core research thesis survives: some measured memory-governance
capabilities depend materially on benchmark-supplied semantics, so benchmark
results should attribute capabilities to product, adapter, runner, reader,
and scorer layers. The claim is bounded to the tested providers, pins,
corpus, prompts, and reader.

## 2. Exact research question

Primary RQ: when a memory benchmark supplies governance semantics outside the
memory product, how much can those supplied semantics change the measured
correctness of the evaluated system?

Secondary questions:

- RQ2: which governance properties are most sensitive to benchmark assistance?
- RQ3: can a benchmark report a successful capability when the product does
  not natively represent or enforce it?
- RQ4: which layer implements each observed capability: product, adapter,
  runner, reader, or scorer?

## 3. Hypotheses

All effects are assisted minus unassisted:

- H-AUTH: authority metadata plus governance instructions increase
  authority-conflict correctness by at least 0.05.
- H-PROV: provenance metadata plus instructions increase source correctness
  by at least 0.05.
- H-TEMP: benchmark as-of filtering increases temporal correctness by at
  least 0.05 or moves future leakage from nonzero to zero.
- H-SCOPE: benchmark principal/scope filtering reduces cross-principal
  exposure or unauthorized answering.
- H-DELETE: product-native deletion, not scorer suppression, removes deleted
  evidence.
- H-NULL: no property shows a material difference.

## 4. Preregistration

The preregistration (`protocols/capability-attribution-v1/preregistration.md`)
was committed at `4749319` on 2026-08-07, before any hidden TEST access. It
freezes provider pins, query IDs, ablation cells, reader settings, three
replicates, statistics, the materiality rule, the USD 2.00 ceiling, and stop
conditions. A single deviation was later recorded: the user-directed
interruption of the first GBrain TEST pack, preserved as
`pack-1-interrupted-20260807T125245` and excluded from analysis. Two abandoned
DeepSeek calls (1,682 input / 1,711 output tokens, USD 0.000715) remain in the
GBrain ledger and in total cost accounting. No hidden response outcome was
inspected before the rerun decision.

Because `deviations.md` joined the protocol directory, the protocol directory
hash changed from the preregistered `6c419bb3...` to `6ffa915a...`. The
preregistration content itself is unchanged.

## 5. Providers and versions

| Provider | Pinned upstream commit | Version | Controlled configuration |
|---|---|---|---|
| GBrain | `15b9863d13635d173562a54f55a1d388bfcf546b` | 0.42.73.2 | PGLite, `--no-embedding`, keyword search, adapter-written Markdown/frontmatter |
| Mem0 OSS | `3f39fba28f7781aaf581f64a4af39d017af65835` | 2.0.17 | `infer=False`, local Chroma, FastEmbed BAAI/bge-small-en-v1.5, telemetry disabled |
| Hindsight | `797faf7981ce9332e2ce7c922471b72b506b4065` | 0.8.6 | LLM features off, local embeddings/reranker, one isolated bank per pack |

No provider was upgraded or patched. Provider-native extraction was not
enabled; the study isolates benchmark assistance while source memories and
provider state stay fixed.

## 6. Query and category selection

Selection is category- and generator-position-based and was frozen before
TEST. Per pack: authority `query_0050/0051`, provenance `query_0056`, temporal
`query_0001` through `query_0012`, scope `query_0054/0055/0059`, deletion
`query_0052/0053`. The same suffixes apply to `pack1`, `pack2`, `pack3`
prefixes: 60 unique TEST queries, 20 per pack. Selection did not use provider
outcomes. Hidden TEST commitment hashes matched for every pack.

## 7. Experimental design

For each provider and pack: clean isolated state, one controlled ingestion
batch, native delete events applied through the adapter lifecycle mapping,
one frozen state hash, then paired retrieval per query with pre/post state
hash checks. All paired conditions share the same raw retrieval call, item
order, text, scores, token budget, query, reader, temperature, seed, and
replicate index.

- Authority and provenance use a 2 by 2 grid: metadata absent/present crossed
  with neutral/governance prompt.
- Temporal uses native retrieval versus benchmark eligibility filtering
  (GBrain and Mem0 only).
- Scope uses native retrieval versus benchmark principal/scope post-filtering
  (all three).
- Deletion is descriptive: native delete mechanism, adapter mapping, raw
  retrieval after deletion, and benchmark filter contribution.

## 8. Authority ablation

| Provider | M0P0 | M0P1 | M1P0 | M1P1 | Delta M0P0 to M1P1 |
|---|---:|---:|---:|---:|---:|
| GBrain | 0.667 | 1.000 | 1.000 | 1.000 | +0.333 |
| Mem0 | 0.833 | 1.000 | 1.000 | 1.000 | +0.167 |
| Hindsight | 0.889 | 1.000 | 1.000 | 1.000 | +0.111 |

Wrong-authority selection: 5 (GBrain), 1 (Mem0), 2 (Hindsight) in M0P0; zero
in every metadata or instruction condition. Abstention dropped to zero in all
assisted cells. Answer change rate: 0.333 / 0.167 / 0.111.

Metadata alone and instruction alone each produced the full observed gain for
GBrain (+0.333 each), with a negative interaction (-0.333). No authority
contrast is material under the strict rule (Holm p 1.0, discordant pairs 0 to
2, McNemar p 0.5 to 1.0). Six queries per provider and ceiling effects bound
the resolution. The directional evidence says both benchmark metadata and
reader instruction improve authority reasoning, with the reader supplying
the actual judgment.

## 9. Provenance ablation

| Provider | M0P0 | M0P1 | M1P0 | M1P1 | Delta M0P0 to M1P1 |
|---|---:|---:|---:|---:|---:|
| GBrain | 0.000 | 0.000 | 1.000 | 0.889 | +0.889 |
| Mem0 | 0.000 | 0.000 | 1.000 | 1.000 | +1.000 |
| Hindsight | 0.000 | 0.000 | 1.000 | 1.000 | +1.000 |

The governance prompt alone changed nothing. Metadata alone carried the entire
effect (metadata-neutral +1.000 for Mem0 and Hindsight, +1.000 for GBrain;
prompt-text-only 0.000 everywhere). Answer change rate 1.000 for all three.

The preregistration declares provenance underpowered (three queries per
provider; McNemar p 0.25, Holm p 0.75, discordant 3). Statistically
unresolved, but the direction is unambiguous and identical across providers:
source identification is impossible from product-exposed text alone and
becomes possible only when the benchmark supplies source metadata.

## 10. Temporal ablation

| Provider | C0-native | C1-assisted | Delta | Holm p | Bootstrap CI | Material |
|---|---:|---:|---:|---:|---:|---|
| GBrain | 0.537 | 1.000 | +0.463 | 3.1e-05 | 0.426 to 0.491 | YES |
| Mem0 | 0.528 | 1.000 | +0.472 | 3.0e-05 | 0.435 to 0.500 | YES |

Future evidence count: GBrain 558 to 0; Mem0 618 to 0. Future-answer leakage:
GBrain 45 to 0; Mem0 49 to 0. Answer change rate 0.463 / 0.472. All 72
retrieval pairs changed under assistance. This is the strongest result:
current/historical-state resolution and future-information blocking are
benchmark-runner functions in this harness, not product capabilities of the
tested configurations.

Hindsight is descriptive only: its pinned recall API requires an
application-supplied `query_timestamp`, so a parameter-free native condition
is not a meaningful configuration. Temporal status is recorded as
`descriptive-application-timestamp-required`.

## 11. Scope ablation

| Provider | D0-native | D1-assisted | Delta | Cross-principal evidence | Unauthorized answers |
|---|---:|---:|---:|---:|---:|
| GBrain | 0.333 | 1.000 | +0.667 | 306 to 0 | 18 to 0 |
| Mem0 | 1.000 | 1.000 | 0.000 | 0 to 0 | 0 to 0 |
| Hindsight | 0.333 | 1.000 | +0.667 | 483 to 0 | 18 to 0 |

The correctness delta fails the strict gate for GBrain and Hindsight
(McNemar p 0.031, Holm p 0.094, CI 0.545 to 0.857), but the preregistered
security-count exception applies: cross-principal evidence and unauthorized
answers transition from clearly nonzero to zero. Mem0's native `user_id`
filter already isolates principals, so benchmark assistance adds nothing to
correctness and Mem0's raw evidence retains its native filter. Future
evidence in the scope set also drops to zero under assistance (GBrain 48,
Hindsight 87, Mem0 36).

Attribution: Mem0's principal isolation is product-native; GBrain's global
CLI search and Hindsight's single-bank recall are not, and their isolation in
this benchmark is adapter/runner-supplied.

## 12. Deletion attribution

All three providers expose a native delete mechanism and the adapter maps
each abstract delete event to that mechanism. After product-native deletion,
raw retrieval returns zero deleted evidence for every provider and query,
without benchmark post-filtering:

| Provider | Deletion queries | Raw deleted evidence | Assisted deleted evidence |
|---|---:|---:|---|
| GBrain | 6 | 0 | 0 |
| Mem0 | 6 | 0 | 0 |
| Hindsight | 6 | 0 | 0 |

Deletion operation is PRIMARY product; lifecycle mapping is CONTRIBUTES
adapter; verification is runner. There was no scorer suppression: the scorer
received the raw retrieval set and the deleted-event IDs were only used to
count exposure, not to remove evidence.

## 13. Reader-prompt / metadata interaction

For authority and provenance the 2 by 2 decomposition separates metadata from
instruction. Two patterns appear:

- Authority: metadata and instruction are substitutable; each alone reaches
  the ceiling, and interaction deltas are negative (-0.333, -0.167, -0.111).
- Provenance: metadata alone is necessary and sufficient; instruction alone
  contributes nothing.

The instruction effect is therefore property-dependent, and both channels are
benchmark-layer contributions rather than product behavior.

## 14. Quantitative results

Complete per-condition rates, contrasts, bootstrap intervals, exact McNemar,
Holm adjustments, reliability fields, and observation counts are in:

- `runs/followups/capability-attribution-v1/test/analysis/analysis.json`
- `runs/followups/capability-attribution-v1/test/analysis/analysis-blinded.json`
- `runs/followups/capability-attribution-v1/test/analysis/data-quality.json`

Blinded QA was performed on `analysis-blinded.json` before the unblinded file
was read. Key totals: 918 attempt rows, 144 retrieval observations, 18
deletion observations, 8 reader errors (all retained in denominators), zero
retrieval mutation failures, all manifest hashes verified.

Reliability: three replicates per cell; pass@1 and all-success rates are
reported per cell in the condition tables. Reader errors (transient gateway
connection aborts after retries) affected 8 of 918 attempts and were scored
as failures, per the preregistration.

## 15. Capability Attribution Matrix

Vocabulary: PRIMARY, CONTRIBUTES, VERIFIES, NOT INVOLVED, NOT OBSERVABLE,
UNSUPPORTED. Cells list the dominant attribution; per-provider notes follow.

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

Provider-dependent cells:

- Principal isolation: Mem0 PRIMARY (native `user_id` filter); GBrain and
  Hindsight UNSUPPORTED natively, with the benchmark runner supplying it.
- Scope filtering: same split; Mem0's native filter covers the user
  dimension, while benchmark scope equality is runner-supplied for all three.
- Authority and provenance representation: products store the fields the
  adapter wrote (GBrain frontmatter, Mem0 metadata dict, Hindsight metadata
  payload), so CONTRIBUTES; the semantic labels, authority ranking, and
  event-catalog mapping are adapter PRIMARY.

Textual justification: every cell above follows the evidence in sections
8 to 13. Cells marked VERIFIES performed a check (state hashes, exposure
counts, typed scoring) rather than supplying the capability.

## 16. Failure analysis

- Reader-model failures: 8 of 918 attempts (GBrain 5, Mem0 3, Hindsight 0)
  after transient gateway connection aborts exhausted two retries. Retained
  in denominators; no pattern by property.
- Infrastructure: gateway-side `ConnectionAbortedError` traces during heavy
  DeepSeek response windows; client-side retries recovered all other calls.
- No ingestion, extraction, retrieval, lifecycle, permission, or benchmark
  failures occurred. Zero retrieval mutation failures; zero state-hash
  mismatches.

## 17. Threats to validity

- Small provider count (three) and one benchmark architecture.
- Synthetic corpus with 60 hidden queries; temporal results rely on 36
  queries per provider, authority on 6, provenance on 3.
- Single common reader (deepseek-v4-flash); reader capability bounds
  text-only conditions, so unassisted scores are lower bounds on what a
  stronger reader could do with raw text.
- Adapter metadata representation choices determine what is "benchmark
  supplied"; a different adapter could shift the product/adapter boundary.
- Metadata and instruction interact; authority effects are partly
  substitutable, so per-channel attribution is not additive.
- Multiple comparisons handled by Holm within property families.
- Native/configuration ambiguity (for example Hindsight's required
  `query_timestamp`, Mem0's required `user_id`) is reported rather than
  manufactured into failures.
- Absence of a native capability is recorded as UNSUPPORTED, not as a
  failure, and application-level extensibility is not treated as product
  capability.
- No independent reproduction by a second lab.

## 18. Comparison with prior work

Sources: primary papers and official repositories recorded in
`docs/research/2026-08-05-benchmark-landscape-and-protocol.md` and the frozen
publication-readiness review, plus live web verification of AMB,
LongMemEval, STATE-Bench, MemBench, MemSecBench, and GateMem.

- AMB: overlaps on the ingest/retrieve/generate/judge pipeline and warns that
  model and prompt choices move scores. This experiment quantifies a
  narrower claim AMB does not isolate: benchmark-supplied governance
  semantics, not just model/prompt choice, move measured capability.
- LongMemEval: overlaps on temporal and update-sensitive questions and oracle
  design. It does not attribute temporal filtering to the benchmark layer;
  our temporal result quantifies exactly that.
- STATE-Bench: overlaps on stateful task evaluation and reliability metrics.
  It does not decompose capability ownership; our matrix is the different
  contribution.
- MemBench, MemSecBench, MPBench: overlap on lifecycle and memory-security
  evaluation. They test whether systems fail; we test which layer supplied a
  passed capability.
- GateMem, AuthMem-Bench: overlap on authority and multi-principal access
  control. AuthMem-Bench holds content fixed and varies authority; our
  authority/provenance ablation holds retrieval fixed and varies benchmark
  metadata and instructions.
- SovereignPA-Bench: overlap on sovereignty framing. Our contribution is the
  quantitative layer accounting rather than another scoreboard.
- memorywire/AMP: provides an interchange architecture for memory objects;
  we do not test it here and we do not claim portability findings.
- IETF AIMEM and ApertoMemory drafts, W3C AI Agent Memory Interoperability
  Community Group: define interchange metadata surfaces; this experiment is
  evidence for requirements discussion but tests no draft.
- "Are we ready for an agent-native memory system" style critiques and AMB
  maintainer warnings establish that harness effects exist; we add a
  memory-specific quantitative measurement of the effect size per property.

What we must not claim: "first" anything, a general harness-effect discovery,
or that providers lack capabilities outside the tested configurations.

## 19. What claims are supported

- Some measured memory-governance capabilities depend materially on
  benchmark-supplied semantics (temporal filtering, principal isolation,
  provenance representation in this harness).
- Benchmark results should attribute capabilities to product, adapter,
  runner, reader, and scorer layers; the matrix in section 15 is the
  instrument.
- Product-native deletion and Mem0's native user filter are genuine product
  capabilities in the tested pins.

## 20. What claims are not supported

- Authority and provenance materiality by the strict statistical gate
  (underpowered; directional only).
- Any aggregate governance score or provider ranking.
- Any statement about capabilities outside the tested providers, pins,
  corpus, prompts, and reader.
- Any claim that the products cannot supply the assisted semantics in other
  configurations.

## 21. Publication implications

The material temporal effect and the qualitative scope-leakage elimination
support a paper whose thesis is that memory-governance benchmark numbers must
carry layer attribution. The provenance metadata dependency is a candidate
secondary finding once replicated with more queries. See
`docs/reports/final-publication-decision.md` for venue-by-venue status.

## 22. Reproduction instructions

Environment: Windows host, repository `.venv`, pinned providers, Docker
Compose for Hindsight. Commands:

```powershell
# GBrain (needs pinned GBrain CLI via Bun)
$env:GBRAIN_BIN="$env:USERPROFILE\.bun\install\global\node_modules\gbrain\src\cli.ts"
$env:BUN_BIN="$env:USERPROFILE\.bun\bin\bun.exe"
.\\.venv\\Scripts\\python.exe -B scripts\\run_capability_attribution.py --provider gbrain --split test

# Mem0
.\\.venv\\Scripts\\python.exe -B scripts\\run_capability_attribution.py --provider mem0 --split test

# Hindsight
$env:HINDSIGHT_API_LLM_PROVIDER='none'
docker compose -f docker\\providers\\hindsight\\docker-compose.yml -p hindsight up -d db api
docker start hindsight-api-proxy-1
$env:HINDSIGHT_API_URL='http://127.0.0.1:8000'
.\\.venv\\Scripts\\python.exe -B scripts\\run_capability_attribution.py --provider hindsight --split test
docker compose -f docker\\providers\\hindsight\\docker-compose.yml -p hindsight stop

# Analysis (blinded file is written first)
.\\.venv\\Scripts\\python.exe -B scripts\\analyze_capability_attribution.py
```

The runner requires `SOVBENCH_DEEPSEEK_API_KEY`, a clean Git tree for TEST,
and the pinned provider artifacts. Every run writes manifests, hashes,
ledgers, and gateway traces under `runs/followups/capability-attribution-v1/`.

## 23. Cost

| Provider | Requests | Input tokens | Output tokens | Cost USD |
|---|---:|---:|---:|---:|
| GBrain (incl. 2 abandoned) | 385 | 609,000 | 331,715 | 0.178140 |
| Mem0 | 381 | 676,703 | 298,234 | 0.178244 |
| Hindsight | 162 | 328,656 | 85,810 | 0.070039 |
| Total | 928 | 1,614,359 | 715,759 | 0.426423 |

All calls returned model identity `deepseek-v4-flash`. The USD 2.00
preregistered ceiling was not approached. Pricing: 0.14 USD/M input,
0.28 USD/M output. No other paid services or cloud costs.

## 24. Final stop decision

A material capability-attribution effect was observed for temporal filtering
and a qualitative material leakage transition for principal/scope isolation.
The preregistered maximum claim applies. The memory research phase ends here:
no additional provider, dataset, model, migration study, enterprise
benchmark, STATE-Bench integration, portability framework, or benchmark
expansion is started. Out-of-scope observations are recorded under
`docs/reports/final-publication-decision.md` as future work.
