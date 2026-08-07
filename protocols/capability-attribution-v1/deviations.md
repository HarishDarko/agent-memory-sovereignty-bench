# Capability Attribution Ablation v1 — Deviations

**Status:** RECORDED BEFORE HIDDEN TEST RERUN
**Date:** 2026-08-07
**Preregistration commit:** `47493191daa11cc02549f997742dd5b82e5214c8`
**Implementation freeze commit:** `d97300b29697ce34c52a6ced163c7a95922363ec`
**Handover commit:** `021961cad8ea8b9a7b16eec8e201ade08838eb20`

This file records the only deviation from the frozen protocol: a user-directed
interruption of the first GBrain hidden TEST pack and the resulting rerun.
No hypothesis, query selection, provider, prompt, metric, threshold, or
analysis rule changed. This record predates the restarted hidden TEST run.

## 1. Event

On 2026-08-07 the GBrain hidden TEST run started at 16:52:45 UTC from the
frozen implementation commit `d97300b`. The user asked the executing agent to
stop and hand over. The agent interrupted the process and exited. No repository
Python or Bun process remained after interruption, and no Hindsight container
was running.

## 2. Abandoned artifact

The interrupted run created only `pack-1` under
`runs/followups/capability-attribution-v1/test/gbrain/`:

- manifest status: `running`
- manifest start: `2026-08-07T16:52:45.296470+00:00`
- scored attempt rows: none (`attempts.jsonl` absent)
- retrieval, deletion, or analysis artifacts: none
- provider state created by ingestion: present (1,496 files, GBrain home with
  Markdown brain and PGLite)

## 3. Abandoned API calls

The shared GBrain ledger (`runs/followups/capability-attribution-v1/test/gbrain/ledger.jsonl`)
contains exactly two DeepSeek reader calls made before interruption:

| # | entry_hash | prompt tokens | completion tokens | returned model |
|---|---:|---:|---:|---|
| 1 | `f51916955180d4009b58a8376761fcb98612aacb0229a7196087b27d1db43313` | 611 | 1182 | deepseek-v4-flash |
| 2 | `52c5ec2dd8a2f16c9dcefcd369723ed09fa61c766cc5158ab01efff782b4dce7` | 1071 | 529 | deepseek-v4-flash |

Total: 1,682 input tokens, 1,711 output tokens, estimated cost USD 0.000715
at the frozen prices (0.14 USD/M input, 0.28 USD/M output).

The ledger stores hashes, identity, and usage only. It never stores request or
response content. No hidden response outcome was inspected before, during, or
after preservation.

## 4. Preservation

The abandoned pack directory was moved, not deleted, to:

`runs/followups/capability-attribution-v1/test/gbrain/pack-1-interrupted-20260807T125245`

Hashes recorded at preservation time:

| Artifact | SHA-256 |
|---|---|
| `pack-1-interrupted-20260807T125245` directory digest (1,496 files, sorted relative-path manifest) | `9E2123BA59776F34AE252989BD701EC28D89C8C0C326D5220E829C105DF9FC0E` |
| preserved `manifest.json` | `3A17C6C8010991D56FEB6F78A988D1DB777096ACA46408A674A4ED1D3DB2E08A` |
| GBrain ledger at preservation time | `164A31C00B253084E7CA12ECC7C957120D3D5812D8700B8CE3CAA002D6A16083` |
| `gateway-neutral.jsonl` at preservation time (contains only abandoned calls) | `BE2AB2E4DCD58885317B7AE34DF42953DAE0683A8978AEE97ABDEA878A2F85F9` |

The directory digest hashes each file, then hashes the sorted
`<sha256>  <relative-path>` manifest. The ledger and gateway trace files remain
in place because both are opened in append mode by the benchmark code; the
rerun appends to them, so abandoned-call accounting and tracing survive.

## 5. Analysis exclusion

The abandoned pack is excluded from the analysis. The analyzer reads only
completed manifests under the three canonical pack names (`pack-1`, `pack-2`,
`pack-3`), so the renamed directory cannot enter any result table.

## 6. Cost accounting

The abandoned calls remain in the GBrain ledger and therefore inside
`_existing_experiment_cost()`, which the gateway uses to enforce the frozen
USD 2.00 ceiling. The rerun starts with the ceiling reduced by USD 0.000715.

## 7. Rerun decision

The rerun uses the frozen implementation and protocol unchanged:

- same query selection (60 TEST queries, category and generator-position
  based, fixed at preregistration);
- same pinned providers and configurations;
- same reader (`deepseek-v4-flash`, temperature 0.0, 2048 evidence tokens,
  3 replicates, 2 retries);
- same prompts, scoring, statistics, materiality rule, and stop conditions;
- clean provider state per pack (fresh `pack-1` directory on rerun);
- one ledger chain containing abandoned and rerun calls.

The interruption and rerun are procedural, not methodological. They do not
constitute evidence selection: no outcome was observed before the rerun
decision.
