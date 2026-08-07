# Independent Review Package — Capability Attribution Ablation v1

**Date:** 2026-08-07

This package lets an external reviewer assess Capability Attribution Ablation
v1 without access to private gold. Public reports contain no gold answers,
no private paths, and no secrets.

## Research questions

1. When a memory benchmark supplies governance semantics outside the memory
   product, how much can those supplied semantics change measured
   correctness?
2. Which governance properties are most sensitive to benchmark assistance?
3. Can a benchmark report a successful capability when the product does not
   natively represent or enforce it?
4. Which layer implements each observed capability: product, adapter, runner,
   reader, or scorer?

## Exact pinned versions

| Component | Pin |
|---|---|
| GBrain | commit `15b9863d13635d173562a54f55a1d388bfcf546b`, v0.42.73.2 |
| Mem0 OSS | commit `3f39fba28f7781aaf581f64a4af39d017af65835`, v2.0.17 |
| Hindsight | commit `797faf7981ce9332e2ce7c922471b72b506b4065`, v0.8.6 |
| Reader | `deepseek-v4-flash` (rolling alias), temperature 0.0, evidence budget 2048 tokens |
| Preregistration | commit `47493191daa11cc02549f997742dd5b82e5214c8` |
| Implementation freeze | commit `d97300b29697ce34c52a6ced163c7a95922363ec` |
| Run code | commit `97f1f81974e0d32f417fd959db1c8bc946c0fcae` (all nine TEST packs) |
| Protocol directory hash | `6ffa915a9e0913d4b0335100a5bd0c7d46b76d4943033c8b6255da4c456a0576` (includes `deviations.md`) |

## Reproduction commands

See `docs/reports/capability-attribution-v1.md` section 22. Summary:

```powershell
.\\.venv\\Scripts\\python.exe -B scripts\\run_capability_attribution.py --provider gbrain --split test
.\\.venv\\Scripts\\python.exe -B scripts\\run_capability_attribution.py --provider mem0 --split test
# Hindsight: start pinned compose stack, then
.\\.venv\\Scripts\\python.exe -B scripts\\run_capability_attribution.py --provider hindsight --split test
.\\.venv\\Scripts\\python.exe -B scripts\\analyze_capability_attribution.py
```

`SOVBENCH_DEEPSEEK_API_KEY` must be set. TEST runs require a clean Git tree.
All artifacts land under `runs/followups/capability-attribution-v1/` with
manifests, hashes, ledgers, and gateway traces.

## Files

- `key-results.md` — capability matrix and key result tables
- `threats-and-errata.md` — threats to validity and the deviation/errata trail
- `reviewer-checklist.md` — the reviewer checklist
- `provider-configs/gbrain.md`, `provider-configs/mem0.md`,
  `provider-configs/hindsight.md` — provider configuration summaries for
  maintainer verification

## Canonical results

`docs/reports/capability-attribution-v1.md` is the canonical report.
Interpretation constraints on the results are documented in
`docs/scientific-audit.md`.
