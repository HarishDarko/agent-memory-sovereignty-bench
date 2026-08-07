# Reader-Protocol Pilot — Protocol (Task 4)

**Status:** Ready for the cost gate. The harness, cases, configs, and cost
estimate are committed and verified offline. The live step requires explicit
user approval, an API key, and `SOVBENCH_PILOT_COST_APPROVED=1`.

## Purpose

Calibrate and freeze the stateless reader before any memory provider is scored.
The pilot is provider-independent: it measures the reader protocol (prompt +
model settings) on oracle-answerable, abstention, authority-conflict, and
temporal-validity cases. The chosen setting becomes the controlled-track
reader default; the decision comes only from the data produced here.

## Cases (20, provider-independent)

| Kind | Count | What it measures |
|---|---:|---|
| oracle_answerable | 8 | Reader answers correctly when evidence is complete |
| no_memory_abstention | 8 | Reader abstains when there is no evidence |
| authority_conflict | 2 | Reader prefers `user_explicit` over lower authority and cites it |
| temporal_validity | 2 | Reader uses validity windows vs the question's as-of |

All names, values, and tokens are synthetic. Evidence ordering is a
serialization choice; the reader prompt never instructs positional reasoning.
Expected answers are public by design: this is reader calibration, not the
hidden TEST split.

## Preregistered settings to compare (3 variants)

Fixed for every variant: `deepseek-v4-flash`, stateless single request,
JSON output, token budget 2048, official DeepSeek API through the policy-gated
proxy.

| Name | thinking | reasoning_effort | temperature |
|---|---|---|---|
| thinking-high-temp0 | enabled | high | 0.0 |
| no-thinking-temp0 | disabled | - | 0.0 |
| thinking-high-temp0.2 | enabled | high | 0.2 |

Parameters the API does not support are recorded, not silently dropped.

## Selection hierarchy (preregistered)

1. JSON validity (parseable structured output)
2. Oracle correctness (answerable cases)
3. No-memory abstention correctness
4. Evidence-ID validity (cited IDs are provided; expected IDs are cited)
5. Mean token usage (tie-breaker)

## Repeats and nondeterminism

Each case is repeated 3 times per variant. If any case's outcome differs
across repeats for the selected variant (material nondeterminism), scored runs
must use 5 reader replicates, and the protocol document records that decision
here before TEST opens.

## Cost estimate (verified 2026-08-06)

Official pricing (https://api-docs.deepseek.com/quick_start/pricing): input
$0.14 / 1M tokens (cache miss), output $0.28 / 1M tokens. Prices were verified
on 2026-08-06 and are time-sensitive; re-verify before the live run.

Worst case with the actual serialized prompts and generous thinking-token
estimates (8,000 output tokens per thinking request, 400 otherwise):

- requests: 20 cases x 3 variants x 3 repeats = **180**
- estimated cost: **about $0.30 maximum** (computed exactly by
  `estimate_cost`; see the pilot result file)
- hard cap: **USD 1.00**, enforced fail-closed by the gateway proxy budget
  (per-run cost ceiling in `config/gateway-policy.toml`)

The user must approve this maximum cost and supply the key before any paid
request. Credits are never purchased by the benchmark.

## Execution

```powershell
# $0 plumbing verification (offline stub):
uv run --frozen python -m benchmark.reader_validation --mode dry-run

# Live pilot (after approval + key):
$env:SOVBENCH_DEEPSEEK_API_KEY = "<key>"
$env:SOVBENCH_PILOT_COST_APPROVED = "1"
uv run --frozen python -m benchmark.reader_validation --mode live
```

Live traffic goes through the in-process policy-gated proxy; the hash-chained
redacted ledger lands at `experiments/reader-pilot/ledger.jsonl` and the
aggregate result at `experiments/reader-pilot/results/pilot-live-*.json`.

## What gets committed after the live run

- this protocol, the cases, and the configs (already committed);
- the redacted ledger (hashes and identity/usage only — never the key, never
  raw content);
- the aggregate pilot result with the selected setting and the
  nondeterminism decision;
- the frozen prompt hash and settings in the protocol/freeze record.

## Model identity

The requested alias is `deepseek-v4-flash`; the expected dated release is
DeepSeek-V4-Flash-0731. Attestation is in `rolling` mode unless the returned
model evidences the release, in which case `strict` becomes possible. The
manifest records requested and returned identity per request.

## Result (live pilot, 2026-08-06)

The approved live pilot ran 180 requests through the policy-gated proxy
(20 cases x 3 variants x 3 repeats). Ledger chain verified intact; all 180
responses returned request IDs; zero errors.

### Aggregates

| Variant | json | oracle | abstain | evidence-id | mean tokens |
|---|---:|---:|---:|---:|---:|
| thinking-high-temp0 | 1.0 | 1.0 | 1.0 | 0.95 | 849.1 |
| no-thinking-temp0 | 1.0 | 1.0 | 1.0 | 0.95 | 737.1 |
| thinking-high-temp0.2 | 1.0 | 1.0 | 1.0 | 0.95 | 756.6 |

No material nondeterminism across repeats; 3 reader replicates remain the
scored-run default.

### Selection (preregistered hierarchy)

**no-thinking-temp0** - ties on JSON validity, oracle, abstention, and
evidence-ID validity; lowest mean tokens (737.1). Frozen into
`config/default.toml` (thinking disabled, temperature 0.0).

### Cost and identity

- Actual spend at official prices: **USD 0.0258** (97,119 input + 43,450
  output tokens), inside the USD 1.00 cap.
- Every response returned model `deepseek-v4-flash` - the rolling alias. The
  API response does not evidence the dated release string, so attestation
  stays `rolling` and every manifest labels results as "rolling alias
  observed on 2026-08-06", never as the 0731 checkpoint.
- Redacted ledger: `experiments/reader-pilot/ledger.jsonl` (hashes, identity,
  usage only - no keys, no raw content).
