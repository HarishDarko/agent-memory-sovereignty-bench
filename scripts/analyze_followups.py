"""Generate the additive post-freeze follow-up reports from observed artifacts."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GBRAIN_RESULT = ROOT / "runs" / "followups" / "gbrain-native-local" / "dev-analysis.json"
SEM_ROOT = ROOT / "runs" / "followups" / "semantic-exit-v1"
SEM_REPORT = ROOT / "docs" / "reports" / "semantic-memory-exit-v1.md"
GBRAIN_REPORT = ROOT / "docs" / "reports" / "gbrain-native-local-supplement.md"


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _latest_attempt() -> Path:
    attempts = [p for p in SEM_ROOT.glob("attempt-*") if (p / "analysis-input.json").exists()]
    if not attempts:
        raise FileNotFoundError("no completed semantic-exit attempt")
    return sorted(attempts, key=lambda p: p.stat().st_mtime)[-1]


def _git_head() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()


def _git_status() -> str:
    return subprocess.run(["git", "status", "--short"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip() or "clean at report generation"


def _money(value: float) -> str:
    return f"${value:.6f}"


def _ledger_total(roots: list[Path] | None = None) -> dict:
    rows = []
    if roots is None:
        roots = [ROOT / "runs" / "followups" / "gbrain-native-local", SEM_ROOT]
    paths = []
    for root in roots:
        paths.extend(root.rglob("*ledger*.jsonl"))
        paths.extend(root.rglob("ledger.jsonl"))
    for path in set(paths):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                rows.append(row)
    prompt = sum(int((r.get("usage") or {}).get("prompt_tokens", 0) or 0) for r in rows)
    completion = sum(int((r.get("usage") or {}).get("completion_tokens", 0) or 0) for r in rows)
    return {"ledger_rows": len(rows), "prompt_tokens": prompt, "completion_tokens": completion, "total_tokens": prompt + completion, "usd": prompt / 1_000_000 * 0.14 + completion / 1_000_000 * 0.28}


def _table(headers: list[str], rows: list[list[object]]) -> str:
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    out.extend("| " + " | ".join(str(cell).replace("|", "\\|") for cell in row) + " |" for row in rows)
    return "\n".join(out)


def _fidelity_table(results: list[dict]) -> str:
    rows = []
    for prop in results[0]["fidelity"]["summary"]:
        cells = []
        for result in results:
            counts = result["fidelity"]["summary"].get(prop, {})
            cells.append(", ".join(f"{key}={value}" for key, value in sorted(counts.items())) or "not recorded")
        rows.append([prop, *cells])
    return _table(["Property", "GBrain", "Mem0 OSS", "Hindsight"], rows)


def _query_summary(result: dict) -> tuple[int, int, int]:
    rows = result.get("pre_exit_queries", [])
    errors = sum(1 for row in rows if row.get("error"))
    retrieved = sum(1 for row in rows if row.get("retrieved_event_ids"))
    return len(rows), retrieved, errors


def write_gbrain_report() -> None:
    data = _json(GBRAIN_RESULT)
    att = data["attestation"]
    summary = data["summary"]
    cost = _ledger_total([ROOT / "runs" / "followups" / "gbrain-native-local"])
    source_commit = _git_head()
    attestation_table = _table(["Field", "Observed value"], [
        ["GBrain", f"{att['gbrain']['commit']} / {att['gbrain']['version']}"],
        ["Ollama", att["ollama"]["ollama_version"]],
        ["Embedding model", att["ollama"]["model_response"]],
        ["Embedding digest", att["ollama"]["models"][0]["digest"]],
        ["Dimensions", att["configured_embedding_dimensions"]],
        ["Ollama endpoint", att["ollama"]["base_url"]],
        ["Reader", f"{att['reader_model']} through the ledgered gateway"],
        ["Reader local", att["reader_is_local"]],
        ["Hidden TEST touched", att["hidden_test_touched"]],
    ])
    text = f"""# Post-Freeze Supplementary GBrain-Native Local-Embedding Run

**Status:** `POST-FREEZE SUPPLEMENTARY GBRAIN-NATIVE LOCAL-EMBEDDING RUN`
**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}
**Repository state used for this report:** `{source_commit}`
**Frozen V1 baseline:** Task 15 report commit `c3007f4`; frozen protocol/results were not modified.
**Protocol:** `post-freeze-followup-v1`; hidden TEST was not touched.

## Decision

The exact pinned GBrain source supports Ollama embeddings. The chosen local
configuration passed the isolation/preflight checks and completed a DEV-only
run, but DEV Recall@5 was **{summary['recall@5']:.4f}**, below the predeclared
0.85 acceptance guardrail. The local configuration is therefore rejected for
the supplementary hidden TEST run. No hosted embedding fallback, Gemini call,
GBrain upgrade, or protocol-v1 change was made.

## Exact pinned capability finding

The inspected GBrain source was commit `{att['gbrain']['commit']}` / version
`{att['gbrain']['version']}`. Its pinned source includes the Ollama recipe and
the `--embedding-model ollama:<model> --embedding-dimensions N` initialization
path. This conclusion is based on the pinned source, not current master.

## Configuration attestation

{attestation_table}

The embedding model was `snowflake-arctic-embed:335m`, 334M parameters, F16,
1024 dimensions, embedding capability only. The initially pulled
`snowflake-arctic-embed2:latest` was not scored because it stalled while
loading alongside GBrain/PGLite; it was not used as a fallback.

## DEV result

The existing DEV personal split was run with the common `deepseek-v4-flash`
reader, unchanged prompt, evidence budget, clock, and scoring. The optimized
preflight passed. The run completed 80 DEV queries with one follow-up
replicate.

{_table(['Metric', 'GBrain local DEV'], [[key, value] for key, value in summary.items()])}

The required guardrail is not a tuning target. It exists to identify an
obviously broken or badly mismatched local retrieval configuration before any
hidden TEST use. Here the configuration was operational and semantically
retrieving, but not strong enough for a defensible hidden comparison under the
predeclared rule.

## Comparison with the frozen V1 evidence

The frozen controlled V1 report records GBrain at Recall@1 = 0.618 and
Recall@5 = 0.982 under its no-embedding/keyword configuration. It records
BM25 Recall@5 = 1.0 and shows that rank-1, not top-5, is the more discriminating
retrieval dimension. The local-embedding DEV result is not directly comparable
as a hidden-test result, but its lower DEV Recall@5 shows that this particular
local model/configuration did not preserve the controlled GBrain behavior.

This does **not** establish that GBrain is bad, that Ollama embeddings are
generally inadequate, or that hosted embeddings would behave the same. It
only establishes that this pinned GBrain + this pinned local model + this
adapter + this DEV workload did not meet the preregistered acceptance rule.

## Controls and contamination checks

All 11 required preflight results passed. The in-process network check was
marked not applicable and made no container-egress claim. Static compose policy,
gold separation, fresh state, canaries, cross-principal isolation, future
filtering, query mutation, and reader statelessness passed. The no-memory probe
abstained on 5/5 synthetic secrets with zero leakage; the oracle control checked
72 non-abstain queries with zero incomplete evidence chains.

The provider used a separate follow-up root. No hidden TEST artifact, hidden
gold, or V1 result path was used. The reader remained remote DeepSeek; Ollama
was embedding-only.

## Cost and reproducibility

All follow-up gateway activity is ledgered. Across the DEV probes and the
incomplete/restarted DEV attempts, the follow-up GBrain ledger accounts for
{cost['prompt_tokens']:,} input tokens and {cost['completion_tokens']:,} output
tokens in the combined follow-up accounting; the total additional accounting
for this report and the semantic-exit follow-up is reported in the semantic
exit report. No hidden TEST API calls were made for GBrain.

Machine-readable evidence is in the ignored `runs/followups/gbrain-native-local/`
directory, especially `dev-analysis.json` and
`environment-attestation.json`. The reproducible command was:

```powershell
$env:GBRAIN_BIN = "$env:USERPROFILE\\.bun\\install\\global\\node_modules\\gbrain\\src\\cli.ts"
$env:BUN_BIN = "$env:USERPROFILE\\.bun\\bin\\bun.exe"
$env:OLLAMA_BASE_URL = "http://127.0.0.1:4713/v1"
$env:OLLAMA_HOST = "127.0.0.1:4713"
$env:SOVBENCH_PROTOCOL_COST_APPROVED = "1"
python scripts/run_gbrain_native_local.py --split dev
```

## Final GBrain follow-up status

**No hidden TEST supplementary GBrain-native local-embedding result exists.**
The correct status is: technically supported, DEV-validated as operational,
rejected by the preregistered Recall@5 guardrail, and stopped without a
hosted-embedding fallback.
"""
    GBRAIN_REPORT.parent.mkdir(parents=True, exist_ok=True)
    GBRAIN_REPORT.write_text(text, encoding="utf-8")


def write_semantic_report() -> None:
    attempt = _latest_attempt()
    data = _json(attempt / "analysis-input.json")
    results = data["results"]
    by_name = {row["provider"]: row for row in results}
    gbrain = by_name["gbrain"]
    mem0 = by_name["mem0"]
    hindsight = by_name["hindsight"]
    commits = _json(ROOT / "datasets" / "commitments" / "semantic-exit-v1.json")
    cost = _ledger_total()
    final_cost = {name: by_name[name].get("ledger", {}) for name in by_name}
    source_commit = _git_head()
    query_rows = [_query_summary(by_name[name]) for name in ("gbrain", "mem0", "hindsight")]
    report = f"""# Memory Sovereignty Benchmark — Semantic Memory Exit v1

**Date:** {datetime.now(timezone.utc).strftime('%Y-%m-%d')}
**Repository commit used to generate findings:** `{source_commit}`
**Frozen Task 15 report:** `docs/reports/task15-native-track-research-review.md`, commit `c3007f4`
**Frozen protocol:** `protocol-v1-freeze`; this report is additive and does not mutate V1.
**Follow-up protocol:** `sovbench/semantic-memory-exit/1`
**Experiment attempt:** `{attempt.name}`
**Provider/model versions:** GBrain `15b9863d...` / v0.42.73.2; Mem0 OSS `3f39fba...` / v2.0.17; Hindsight `797faf7...` / v0.8.6; common native reader calls used `deepseek-v4-flash` through the existing gateway.
**Dataset:** 24 synthetic public events, 10 public queries; events SHA-256 `{commits['events_sha256']}`; queries SHA-256 `{commits['queries_sha256']}`; private-gold SHA-256 `{commits['private_gold_sha256']}`.
**Repository status at report generation:** `{_git_status()}`

## 1. Executive Summary

This bounded experiment asked what trustworthy memory meaning survives when a
user keeps only the pinned product's documented/native exit artifact, the
original runtime is removed, and the product is reconstructed from that
artifact alone. It used 24 deliberately constructed source events covering
temporal state, authority, provenance, scope, deletion, supersession, and
model-derived facts. It did not create a general migration framework or a
recall leaderboard.

The strongest observation is Hindsight's pinned native export response: the
Category A artifact contained only `{{"version":"1"}}`, and import returned no
created or updated operations. This is a measured export-contract observation,
not proof that no internal state existed. It means the tested documented exit
surface did not expose the memory state needed for recovery.

Mem0's native `get_all` enumeration exposed 17 derived memories for 22
non-delete source events. It was machine-readable, but the native artifact
contained derived memory text and selected metadata rather than the canonical
raw event stream, validity intervals, supersession graph, or deletion
tombstones. Same-system reconstruction re-added 17 memories without rerunning
an LLM, but it was not a lossless raw-event recovery.

GBrain produced 20 human-readable Markdown pages. The tested import path
rebuilt a runtime but returned `No results` for all 10 recovery probes, so
human readability did not imply behavioral recovery. Its exported frontmatter
also reflected the benchmark adapter's selected metadata, not all semantic
event fields.

The evidence supports a layered architecture for user and enterprise memory:
retain a canonical, append-only, semantically rich event ledger under user or
organizational control, and treat memory products as rebuildable indexes or
derived views. It does not justify declaring one provider universally best or
claiming a general portability theorem.

## 2. Frozen V1 Context

Task 15 is treated as a completed, frozen V1. Its controlled and native tables
remain authoritative. The frozen report records controlled GBrain Recall@1
0.618 and Recall@5 0.982, BM25 Recall@5 1.0, native Mem0 Recall@1 falling from
0.600 controlled to 0.418 native, and native Hindsight changing from 0.709 to
0.727. Those facts are used as context only; no V1 result was recomputed or
merged with this follow-up.

The broad Tasks 16–20 roadmap remains stopped. This report covers only the
local-embedding GBrain feasibility follow-up and this small semantic-exit
experiment.

## 3. Exact Research Question

**If a user leaves a memory product and retains only the state that the product
legitimately lets the user keep, how much trustworthy memory meaning survives
after the original application state is gone?**

The experiment separates serialization fidelity, semantic/state fidelity,
behavioral recovery, and governance properties. A successful file copy is not
treated as successful semantic migration.

## 4. GBrain-Native Supplementary Result/Status

The exact pinned GBrain source supports Ollama embeddings. The selected local
model was `snowflake-arctic-embed:335m`, Ollama digest
`21ab8b9b0545e26a78164a910691440a3f1de1bfa41c3953d7451d52036c581a`, 1024
dimensions, Ollama 0.32.6. DEV preflight passed, but DEV Recall@5 was
0.7639, below the preregistered 0.85 guardrail. Hidden TEST was not run. The
complete additive report is [gbrain-native-local-supplement.md](gbrain-native-local-supplement.md).

## 5. Systems and Pinned Versions

{_table(['System', 'Pinned version', 'Exit path used', 'Native LLM during population'], [
['GBrain', '15b9863d... / 0.42.73.2', 'pinned `gbrain export --dir` Markdown', 'none; local Ollama was embedding-only'],
['Mem0 OSS', '3f39fba... / 2.0.17', 'documented/native `Memory.get_all` enumeration per user', 'DeepSeek through gateway, `infer=True`'],
['Hindsight', '797faf7... / 0.8.6', 'pinned native bank `GET /export`', 'DeepSeek through gateway via internal sidecar'],
])}

The existing adapters add event metadata and lifecycle mapping. Those adapter
fields are reported as adapter-mediated evidence, not automatically as native
product guarantees.

## 6. Local Embedding Model and Reader Configuration

GBrain used only the local Ollama embedding model above. It did not run a local
generative model. Mem0 used its pinned local FastEmbed configuration while
native fact extraction used the common `deepseek-v4-flash` gateway. Hindsight
used its pinned local embedding/reranker images while native retain/recall
features used the gateway bridge. No gold answers were sent to any provider or
reader. No LLM judge was used for the exit experiment.

## 7. Synthetic Exit Dataset

The public corpus is `datasets/followups/semantic-exit-v1/`. It contains 24
events and 10 queries, with two principals (`alice`, `bob`), personal/shared
scopes, changed and historical claims, source/event time differences,
authority conflicts, deletion targets, a do-not-store instruction, native/model
inference, a multi-fact source event, a provenance chain, and an ambiguous
claim. Private semantic gold is under `scorer_private/semantic-exit-v1/` and
was never mounted in a provider directory.

## 8. Native Population Behavior

{_table(['System', 'Population operations', 'Pre-exit query probes', 'Observed native behavior'], [
['GBrain', f"{sum(1 for x in gbrain.get('population', []) if x.get('ok'))}/24", f"{query_rows[0][0]} ({query_rows[0][1]} returned records)", 'Markdown pages; deletion removed the targeted pages; no native extraction'],
['Mem0 OSS', f"{sum(1 for x in mem0.get('population', []) if x.get('ok'))}/24", f"{query_rows[1][0]} ({query_rows[1][1]} returned records)", '17 native derived memories enumerated across Alice/Bob; 22 source upserts were not preserved one-for-one'],
['Hindsight', f"{sum(1 for x in hindsight.get('population', []) if x.get('ok'))}/24", f"{query_rows[2][0]} ({query_rows[2][1]} returned records)", 'hybrid native retrieval and retain/reflection calls; export response was version-only'],
])}

## 9. Exit Artifact Definition per Provider

Category A is the primary result: the documented/native surface a technically
capable user could call. GBrain was a Markdown export; Mem0 was native
`get_all`, not the adapter's private event registry; Hindsight was the pinned
bank export endpoint. Category B is a separate copy of run-owned raw state
where practical: GBrain raw brain/PGLite files and Mem0 Chroma/history files;
no Hindsight database volume was treated as a user export.

{_table(['System', 'Category A artifact', 'Human-readable', 'Hash'], [[name, by_name[name]['category_a']['format'], by_name[name]['category_a'].get('human_readable'), by_name[name]['category_a']['sha256']] for name in ('gbrain','mem0','hindsight')])}

## 10. What Was Retained and Destroyed

The retained Category A artifact and its hash remained outside the original
runtime. Category B was retained only as separately labelled disaster-recovery
evidence. Original provider data directories were removed and verified absent.
For Hindsight, the native bank was deleted and the experiment-specific Docker
project and volume were removed before fresh recovery. The first GBrain cleanup
attempt hit a Windows access-denied lock; the exact run-owned directory was
removed and re-verified after the process ended. This is recorded as
`post_run_cleanup_verified`, not hidden.

{_table(['System', 'Original runtime destroyed', 'Recovery runtime', 'Raw Category B'], [[name, by_name[name]['destruction'].get('verified'), by_name[name]['recovery'].get('status'), by_name[name]['category_b'].get('available')] for name in ('gbrain','mem0','hindsight')])}

## 11. Semantic Export Fidelity Matrix

The following is a count of per-event classifications, not a composite score.
It is intentionally exposed dimension by dimension.

{_fidelity_table(results)}

The Hindsight `version=1` artifact makes most properties `LOST` or `NOT
OBSERVABLE`; that is a property of the observed native exit response. The
GBrain and Mem0 preservation of authority, source, principal, and scope must
be read with the adapter caveat: those fields were supplied by the benchmark
adapter and are not proven native guarantees.

## 12. Same-System Recovery Results

{_table(['System', 'Recovery action', 'LLM required', 'Behavioral result'], [
['GBrain', 'Import exported Markdown into a fresh pinned GBrain and run 10 CLI searches', gbrain['recovery'].get('llm_required'), 'Runtime rebuilt, but all 10 searches returned `No results`'],
['Mem0 OSS', f"Re-add {mem0['recovery'].get('memories_readded_without_inference')} enumerated memories with `infer=False`", mem0['recovery'].get('llm_required'), 'Fresh Chroma index rebuilt; native-ID probes recorded after recovery'],
['Hindsight', 'Import native bank export into a fresh bank', hindsight['recovery'].get('llm_required'), 'Import returned no created/updated operations; post-import recall probes were recorded'],
])}

The GBrain result is an important failure to interpret carefully: the artifact
was readable, but the tested pinned import command did not restore observable
search behavior. This may involve source routing, index rebuild semantics, or
adapter/import interaction; it is not enough evidence to assign the cause to
GBrain alone.

## 13. Recovery Nondeterminism

The exit recovery path did not rerun an LLM: Mem0 memories were re-added as
already derived text, GBrain imported Markdown, and Hindsight used the native
import endpoint. Therefore three-repeat regeneration variance was not
applicable to this exact recovery path. Native population itself used one
replicate per provider, so extraction/consolidation nondeterminism was observed
qualitatively but not estimated statistically. A future regeneration study
would need at least three independent recoveries and must not call them
lossless recovery.

## 14. Cross-System Migration Result

No cross-system migration was justified. Same-system exit already exposed
unresolved source-export and recovery failures, while a conversion pair would
have added an adapter-defined mapping and risked hiding whether loss occurred
before serialization or at the destination. No generalized migration code was
built.

## 15. Provenance Fidelity

The synthetic corpus included a source chain for ATLAS-42 and source identifiers
for user, policy, webpage, assistant, and calendar records. GBrain and Mem0
artifacts retained source strings in the tested export shape; Hindsight's
version-only Category A artifact exposed no source state. However, GBrain and
Mem0 source retention was carried through benchmark metadata. The result is
**adapter-mediated preservation**, not proof of a product-native provenance
contract.

## 16. Authority Fidelity

The corpus deliberately conflicted an untrusted webpage with a signed release
policy. The live pre-exit adapters could return both deployment claims, while
the private gold identifies the policy as authoritative. The GBrain/Mem0
exported metadata retained the authority labels supplied by the adapter;
Hindsight's primary export did not expose them. The experiment cannot claim
that the products independently preserve or enforce authority semantics.

## 17. Explicit-User vs Model-Derived Fidelity

The corpus separated explicit user statements from assistant inference and
included an explicit erasure target for a derived claim. Mem0 native extraction
created derived memories, but its `get_all` output did not provide a complete
raw-event-to-derived-memory audit trail. GBrain preserved the adapter's
`authority` field because it was written to frontmatter. Hindsight's version-only
export made this property not observable. No provider's Category A result
should be interpreted as a complete model-inference provenance ledger.

## 18. Temporal and Supersession Fidelity

The source events carried `valid_from`, `valid_to`, `available_at`, correction,
and supersession links. The tested GBrain and Mem0 adapter metadata did not
include all validity or supersession fields, so temporal history was commonly
lost or not observable in Category A. Hindsight's version-only export provided
no evidence of these fields. Retrieval before exit was filtered by the
benchmark adapter and therefore does not prove that native export preserves
as-of or historical-state semantics.

## 19. Scope and Access-Control Fidelity

The experiment used Alice personal, Bob personal, and Atlas shared scope. The
pre-exit adapter queries recorded no provider operation failure, but the
cross-principal behavior was adapter-mediated. Mem0 native `get_all` was
enumerated separately for Alice and Bob. Category A retention of principal and
scope was visible for GBrain/Mem0 through adapter-added metadata and absent in
Hindsight's version-only export. Export portability must therefore be tested
with access-control semantics, not just text files.

## 20. Deletion and Erasure Fidelity

Two explicit delete operations targeted an untrusted external note and an
assistant-inferred claim. The live providers removed the targeted state through
their tested lifecycle calls. No Category A artifact contained a complete
deletion/tombstone record: deletion state was `LOST` for the delete events in
the matrix. The experiment did not find evidence that deleted information
returned after the fresh same-system reconstructions, but Hindsight's empty
export and GBrain's failed search recovery limit the strength of that negative
finding.

## 21. Human Readability

GBrain's Markdown export was directly inspectable and carried page frontmatter
plus text. Hindsight's JSON response was syntactically human-readable but
semantically empty beyond `version=1`. Mem0's JSON `get_all` enumeration was
machine-readable but included generated IDs, hashes, timestamps, and derived
memory text rather than a clean source-event ledger. Human readability and
semantic completeness are separate properties.

## 22. Rebuildability

GBrain and Hindsight accepted a fresh runtime construction path, but the tested
GBrain import produced no search results and Hindsight import produced no
operations. Mem0 rebuilt a Chroma index from 17 derived memories without an
LLM, but raw-event reconstruction and exact native memory identity were not
available from Category A alone. Index rebuildability is therefore not the
same as application-state or semantic rebuildability.

## 23. Costs and Latency

The final complete attempt used no reader judge. Final-attempt ledgered native
calls were approximately Mem0 {final_cost['mem0'].get('calls', 0)} and Hindsight
{final_cost['hindsight'].get('calls', 0)}; GBrain used no DeepSeek calls. Across
all additive follow-up attempts, the ledger accounts for
{cost['prompt_tokens']:,} input tokens, {cost['completion_tokens']:,} output
tokens, and approximately **{_money(cost['usd'])}** at the configured DeepSeek
accounting rates. This includes the corrected reruns and excludes no observed
ledgered usage. Provider latency was recorded per population/query operation
in the machine observations; no composite latency score is reported.

## 24. Failure Analysis

Observed issues are categorized as follows:

- **Harness/configuration failure:** the first semantic attempt used a gateway
  requiring request identity headers that native clients do not send. It was
  stopped, preserved as an incomplete attempt, and excluded from findings;
  Task 15's stamped native gateway mode was applied in the corrected run.
- **Lifecycle/infrastructure failure:** the first GBrain destruction pass hit a
  Windows directory-lock/access-denied condition. The exact runtime was removed
  after process completion and verified absent.
- **Provider/export behavior:** Hindsight's native export response was
  version-only; GBrain import produced no search results; Mem0 exposed derived
  rather than raw event state.
- **Dependency warning:** Mem0 reported that optional spaCy lemma/full models
  were not installed. The pinned native run still completed; this warning is
  recorded and not silently normalized away.

No provider population operation failed in the corrected completed attempt.

## 25. Existing Standards and Prior Work Comparison

The frozen V1 research review already compared LongMemEval, LoCoMo, BEAM, AMB,
MemTools, STATE-Bench, GateMem, MemSecBench, AuthMem-Bench, SovereignPA-Bench,
memorywire/AMP, and IETF AI memory-interchange work. This follow-up reuses that
context rather than claiming a new benchmark category.

Those efforts do better at task-level memory evaluation, security/governance
framing, or proposed interchange semantics. The present experiment measures a
narrow property they do not automatically establish: what the pinned product
actually exposes through its documented/native exit path and whether a fresh
same-system runtime can recover state from that artifact. It does not prove
that an existing interchange format could not preserve the missing properties.

Any future interoperability claim should first test memorywire/AMP or an
applicable IETF interchange representation against this same private gold.

## 26. Limitations

This is 24 synthetic events, one native population replicate, three pinned
providers, and one machine. It uses existing adapters that add metadata and
post-filter retrieval; native product guarantees are not isolated from adapter
behavior. The Hindsight export contract was observed through the pinned
endpoint response, but its internal database is not reverse-engineered here.
The GBrain import probe used the pinned CLI path and observed no results, but
source routing/index behavior deserves independent confirmation. No LLM
regeneration variance, catastrophic application restore, or cross-system
migration was measured. These limits prevent a universal provider ranking.

## 27. Reproduction Instructions

The source corpus and private gold commitments are listed above. The corrected
runner command was:

```powershell
$env:SOVBENCH_PROTOCOL_COST_APPROVED = "1"
$env:GBRAIN_BIN = "$env:USERPROFILE\\.bun\\install\\global\\node_modules\\gbrain\\src\\cli.ts"
$env:BUN_BIN = "$env:USERPROFILE\\.bun\\bin\\bun.exe"
$env:OLLAMA_BASE_URL = "http://127.0.0.1:4713/v1"
$env:OLLAMA_HOST = "127.0.0.1:4713"
$env:PYTHONPATH = ".venv\\Lib\\site-packages"
python scripts/run_semantic_memory_exit.py
```

Generated observations are under `runs/followups/semantic-exit-v1/{attempt.name}`;
the redacted report is this file. The private gold is not a provider artifact.

## 28. Personal/Project-Memory Recommendation

Based on this evidence, if the priority is to change AI agents or memory
software later without losing trustworthy accumulated memory, choose a
**layered approach**: keep a user-controlled canonical event ledger containing
raw source text, timestamps, validity, authority, provenance, principal/scope,
supersession, and deletion/tombstone state; use GBrain, Mem0, or Hindsight as
rebuildable indexes/derived views with an export receipt.

If forced to choose a product layer only, GBrain is the most human-readable
tested exit artifact, but its tested import did not recover behavior. Mem0
offers a practical native enumeration but exposes derived memories rather than
the full source ledger. Hindsight's observed native export was insufficient for
the exit question. None earns a standalone sovereignty recommendation.

## 29. Enterprise-Memory Recommendation

Enterprise use should require vendor independence through a separately owned
canonical ledger and periodic export drills. The ledger must preserve
provenance, authority, temporal history, access-control scopes, deletion and
tombstone state, and an auditable source-to-derived-memory relationship.
Providers may serve retrieval and consolidation, but their indexes should be
rebuildable and disposable. Disaster recovery must test a fresh environment,
not merely the continued availability of the original database volume.

## 30. Final Continue/Stop Recommendation

**Recommendation 2 — PUBLISH V1 + ONE SMALL FOLLOW-UP.** Publish the frozen V1
benchmark together with this narrowly scoped exit reconnaissance, with explicit
adapter and export-contract caveats. Stop the broad Tasks 16–20 roadmap now.
The observed Hindsight export gap, Mem0 derived-state gap, and GBrain
human-readable-but-nonrecovering result are useful enough to publish as
measured engineering evidence, but they do not justify more providers,
enterprise corpora, STATE-Bench integration, or a generalized migration layer
in this project.

The one unresolved human-review decision is whether to perform a separate
manual confirmation of the pinned Hindsight export/import contract before
making public wording stronger than “the tested native endpoint returned a
version-only artifact.”

## Appendix: Machine Evidence and Warnings

- Semantic attempt: `{attempt.name}`.
- GBrain supplementary analysis: `runs/followups/gbrain-native-local/dev-analysis.json`.
- GBrain attestation: `runs/followups/gbrain-native-local/environment-attestation.json`.
- Frozen V1 report: `docs/reports/task15-native-track-research-review.md`.
- Public exit corpus: `datasets/followups/semantic-exit-v1/`.
- Private gold: `scorer_private/semantic-exit-v1/gold.json`.
- No Graphiti, Cognee, MIND-Mem, enterprise corpus, STATE-Bench, or broad
  migration tooling was added.
- The first identity-misconfigured attempt is retained as an incomplete
  diagnostic artifact and is not included in the final result tables.
"""
    SEM_REPORT.parent.mkdir(parents=True, exist_ok=True)
    SEM_REPORT.write_text(report, encoding="utf-8")


def main() -> int:
    write_gbrain_report()
    write_semantic_report()
    print(GBRAIN_REPORT)
    print(SEM_REPORT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
