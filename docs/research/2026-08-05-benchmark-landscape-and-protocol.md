# Memory Sovereignty Benchmark: Research Landscape and Protocol Rationale

**Research date:** 2026-08-05  
**Purpose:** Establish the evidence base for the implementation plan before any real memory provider is installed or scored.  
**Normative principle:** No system is presumed best. Selection, configuration, scoring, exclusions, and claims are fixed before hidden-test results are opened.

## 1. Research question

The benchmark asks whether a memory system can maintain correct, authorized, erasable, evolving, useful, and user-owned state—and whether that state can survive provider loss or replacement. Retrieval accuracy is necessary but not sufficient. The unit under study is a lifecycle:

```text
source events -> stored state -> retrieval evidence -> reader answer -> lifecycle action -> export/recovery/migration
```

A credible evaluation must localize failures to the stage that caused them. A final-answer score alone cannot distinguish bad ingestion, bad retrieval, reader failure, authorization failure, or benchmark contamination.

## 2. DeepSeek identity and experimental role

DeepSeek’s official 2026-07-31 changelog names the dated release **DeepSeek-V4-Flash-0731** and says the public API continues to use the rolling alias `deepseek-v4-flash`. The same source says V4 Pro and app/web models were unchanged by that release. The official API quick start lists `https://api.deepseek.com` as the base URL and supports thinking mode plus a `reasoning_effort` setting.

No official source reviewed here defines “DeepSeek V4 Plus 07-31.” That label may describe a UI plan, router, or third-party alias, but it is not sufficient model identity for a scientific result. Two DeepSeek roles must remain separate:

1. **Implementation agent:** the Codex model used to build the benchmark. Its coding performance does not enter benchmark scores.
2. **Controlled reader:** the stateless model that receives the same normalized evidence and question for every provider. Its exact API identity and settings are experimental variables recorded in the manifest.

DeepSeek reports strong coding-agent performance for V4 Flash 0731 and says its published coding-agent results used a minimal harness, maximum effort, `top_p=0.95`, and `temperature=1.0`. Those are evidence about coding-agent evaluation, not a reason to copy the same sampling settings into a factual memory reader. Reader settings must be selected on DEV by a small, provider-independent oracle/no-memory pilot and frozen before TEST.

Primary sources:

- [DeepSeek API changelog](https://api-docs.deepseek.com/updates/)
- [DeepSeek API quick start](https://api-docs.deepseek.com/guides/reasoning_model)
- [DeepSeek-V4-Flash-0731 model card](https://huggingface.co/deepseek-ai/DeepSeek-V4-Flash-0731)

## 3. What leading benchmarks contribute

### Agent Memory Benchmark (AMB)

AMB provides a useful four-stage pattern—ingest, retrieve, generate, judge—plus oracle mode, latency, token, and cost reporting. Its maintainers also warn that model and prompt changes can move scores materially. The benchmark is maintained by Vectorize, which also develops Hindsight, so its infrastructure is useful but its provider comparisons must be independently reproduced.

Source: [vectorize-io/agent-memory-benchmark](https://github.com/vectorize-io/agent-memory-benchmark)

### LongMemEval

LongMemEval’s 500 questions cover information extraction, multi-session reasoning, knowledge updates, temporal reasoning, and abstention. Its oracle evidence is especially useful for separating retrieval failures from answerability and reader failures.

Source: [LongMemEval official repository](https://github.com/xiaowu0162/longmemeval)

### STATE-Bench

STATE-Bench contributes task-local sandboxes, final-state checks instead of prose-only grading, repeated trials, reliability metrics, cost, and user-experience outcomes. Its Agent Learning Track is relevant to memory retrieval, while the task-local database/tool design is a strong model for the enterprise corpus.

Source: [Microsoft STATE-Bench](https://github.com/microsoft/STATE-Bench)

### GateMem and AuthMem-Bench

GateMem frames memory utility together with multi-principal access control and active forgetting. AuthMem-Bench isolates authority collapse by holding a claim/task fixed while changing source authority. Together they motivate paired cases where content is identical but permission or authority differs.

Sources: [GateMem](https://arxiv.org/abs/2606.18829), [AuthMem-Bench](https://arxiv.org/abs/2608.01679)

### MemSecBench and MPBench

MemSecBench’s Write→Execute→Forget lifecycle, intermediate checkpoints, programmatic gates, and repair assessment show why memory security cannot be reduced to prompt-injection success. MPBench adds multiple write channels, structural vulnerabilities, and aggressiveness/utility trade-offs. These motivate persistent poisoning, provenance laundering, and post-deletion consequence tests.

Sources: [MemSecBench](https://arxiv.org/abs/2607.27080), [MPBench](https://arxiv.org/abs/2606.04329)

### MemoryAgentBench, AMA-Bench, MemoryArena, and WorldMemArena

MemoryAgentBench covers incremental multi-turn operation, conflict resolution, test-time learning, and long-range understanding. AMA-Bench separates memory construction from retrieval over agent trajectories. MemoryArena shows that static recall can saturate while interdependent memory-agent-environment tasks still fail. WorldMemArena’s lifecycle staging and gold evidence chains support stage-level diagnosis.

Sources:

- [MemoryAgentBench](https://github.com/HUST-AI-HYZ/MemoryAgentBench)
- [AMA-Bench](https://github.com/AMA-Bench/AMA-Bench)
- [MemoryArena](https://memoryarena.github.io/)
- [WorldMemArena](https://arxiv.org/abs/2605.29341)

### EvoMemBench and GroupMemBench

EvoMemBench reports that no evaluated memory method is universally best and that long-context baselines remain competitive. GroupMemBench shows that BM25 can match or exceed more elaborate systems in multi-party settings and highlights speaker-grounded beliefs and audience adaptation. These findings justify strong simple baselines and explicit owner/requester/subject fields.

Sources: [EvoMemBench](https://arxiv.org/abs/2605.18421), [GroupMemBench](https://arxiv.org/abs/2605.14498)

### HELM and contamination research

HELM’s core lessons are broad coverage, multiple metrics, standardized adaptation, and prompt-level transparency. Contamination research supports public DEV plus held-back TEST, transparent benchmark cards, generated post-training facts, overlap checks, and explicit marking when cleanliness cannot be proven.

Sources:

- [Stanford HELM](https://crfm.stanford.edu/helm/index.html)
- [Benchmarking Benchmark Leakage](https://arxiv.org/abs/2404.18824)
- [MMLU-CF](https://arxiv.org/abs/2412.15194)

## 4. Provider landscape and neutral selection

The first broad comparison should include simple controls and systems that represent materially different memory architectures:

| System | Role in study | Current research caution |
|---|---|---|
| No-memory | Leakage/abstention control | Not a competing memory system. |
| Oracle | Answerability/reader upper control | Uses gold by design; never ranked. |
| SQLite FTS/BM25 | Strong lexical baseline | Must receive the same lifecycle replay, budget, and scoping rules. |
| Full context | “No retrieval” baseline where feasible | Context budget and truncation must be identical and reported. |
| OptMem | Minimal file-first memory | Very new; treat as experimental, pin commit, inspect scripts before execution. |
| GBrain | Git/Markdown system of record with derived search | Broad feature surface and multiple optional engines increase configuration risk. |
| Mem0 OSS | Fact-extraction memory | Separate OSS from cloud and disable telemetry/external calls. |
| Hindsight | Hybrid semantic/BM25/graph/temporal memory | Vendor-authored benchmark claims require independent reproduction. |
| Graphiti | Temporal knowledge graph specialist | Anonymous telemetry is enabled by default in current documentation; disable and verify egress. |
| Cognee | Graph/semantic specialist | Treat feature claims as hypotheses until measured. |
| MIND-Mem | Governance/audit specialist | New/experimental; pin exact version and report unsupported operations. |

Primary repositories:

- [OptMem](https://github.com/VictorTaelin/OptMem)
- [GBrain](https://github.com/garrytan/gbrain)
- [Mem0](https://github.com/mem0ai/mem0)
- [Hindsight](https://github.com/vectorize-io/hindsight)
- [Graphiti](https://github.com/getzep/graphiti)
- [Cognee](https://github.com/topoteretes/cognee)
- [MIND-Mem](https://github.com/star-ga/mind-mem)

Provider inclusion is not endorsement. Every adapter must pin an upstream commit/image, pass the same compliance suite, publish its config, and expose missing capabilities rather than simulating them.

## 5. Standards landscape correction

The earlier conversation referred to a “Memory Interchange Bundle” as if an IETF standard existed. That claim is not supported. Current sources show multiple proposals and Internet-Drafts, including ApertoMemory and AMP/memorywire. Internet-Drafts are works in progress, not standards. The benchmark should test export fidelity against a benchmark-owned canonical schema first, then map that schema to competing proposals as an interoperability experiment.

Sources:

- [ApertoMemory Internet-Draft](https://www.ietf.org/ietf-ftp/internet-drafts/draft-ferro-apertomemory-02.html)
- [Agent Memory Protocol / memorywire](https://arxiv.org/abs/2606.01138)

## 6. Measurement model

### Stage 1: ingestion and stored state

- accepted, rejected, deduplicated, consolidated, and deleted event counts;
- time-to-ready and timeout/failure rate;
- raw stored-state export where legally and technically available;
- provenance, subject, authority, scope, validity, supersession, and tombstone preservation;
- logical state hash and provider-specific physical snapshot hash.

### Stage 2: retrieval

- gold evidence recall@k as a fraction of the complete chain;
- complete-chain@k;
- precision@k where relevant;
- forbidden-evidence rate and cross-principal leakage rate;
- stale, superseded, expired, deleted, and poisoned evidence rates;
- latency distribution, result count, and retrieval mutation.

### Stage 3: reader

- typed exact/acceptable-answer correctness;
- calibrated abstention and false-answer rate;
- evidence-ID precision/recall;
- authority/provenance correctness;
- model failures, invalid JSON, retries, token usage, and latency.

Offline stub outputs are excluded from semantic reader metrics.

### Stage 4: lifecycle and sovereignty

- deletion persistence across query, restart, export, restore, and migration;
- export coverage and round-trip fidelity;
- recovery point objective, recovery time, and unrecoverable loss;
- A→B migration correctness, provenance retention, permission retention, and duplicate/collision rate;
- storage growth, write amplification, indexing cost, and query cost.

### Reporting rule

Do not collapse all dimensions into a single weighted score unless the weights were preregistered for a specific deployment. Publish a metric matrix, capability coverage, failure rates, and Pareto frontiers. An unsupported required capability is “unsupported,” not silently zero and not silently omitted.

## 7. Statistical protocol

- Use the query/storyline as the paired unit and bootstrap by synthetic person or enterprise case, not by individual correlated turns.
- Report point estimates and 95% paired bootstrap confidence intervals with 10,000 deterministic resamples.
- For binary paired comparisons, report exact McNemar tests as confirmation.
- Apply Holm correction within each declared metric family when making multiple provider comparisons.
- Declare a practical effect threshold before TEST. Statistical significance without practical relevance is not a win.
- Run deterministic local baselines once per frozen artifact plus a reproducibility rerun. Run nondeterministic/async providers and reader generations at least five times where affordable; always report failure and timeout rates.
- Report pass@1 and all-success reliability across repeated trials for operational tasks.
- Never discard failed attempts. Retries, parse failures, timeouts, and manual interventions remain in the denominator.
- A winner claim requires a paired adjusted result beyond the practical threshold on the named metric. Otherwise report “no resolved difference,” not a rank inferred from raw means.

## 8. Contamination and validity controls

The final preflight and analysis must cover at least these channels:

1. Cross-provider volumes, databases, caches, queues, and process state.
2. Query-time mutation, learning, or hidden write-back.
3. Future-event ingestion before historical checkpoints.
4. Public benchmark or pretraining overlap.
5. Gold answers, acceptable aliases, evidence IDs, or scorer code visible to providers/readers.
6. Authority collapse during consolidation.
7. Provenance laundering from low-authority sources.
8. Cross-user, tenant, role, and group leakage.
9. Deletion residues in indexes, summaries, caches, exports, backups, logs, and migrations.
10. Poisoning through user, assistant, tool, document, and imported-memory channels.
11. Self-generated memory feedback loops.
12. Temporal leakage through validity windows, supersession, or wall-clock use.
13. Async-indexing advantages caused by unequal waits or polling.
14. Embedding/model/API caches shared across providers or runs.
15. Context-window cheating or unequal evidence budgets.
16. Reader conversation or request-cache carryover.
17. Judge variance and evaluator-model preference.
18. DEV/TEST tuning leakage and secret seed exposure.
19. Provider, image, dependency, or rolling-model version drift.
20. Retry selection and cost/latency survivor bias.
21. Telemetry or background network calls.
22. Evidence serialization truncation that reports unseen IDs.
23. Subject/requester/owner conflation.
24. Incomplete oracle evidence chains.
25. Benchmark implementation defects that fail open.

## 9. Publication standard

A public result bundle must contain code commit, dirty-tree status, environment lock, container image digests, upstream commits, configs, corpus and prompt hashes, model attestation, preflight evidence, raw traces with private values redacted only through a documented release transform, scores, uncertainty analysis, failures, exclusions, and a reproduction command. The article and LinkedIn summary must be generated from the frozen result tables—not written first and fitted to the data later.

The strongest career signal is not a dramatic winner. It is a benchmark whose negative results, ties, unsupported capabilities, contamination failures, and limitations are as visible as positive findings.
