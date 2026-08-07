# Threats to Validity and Errata Trail

## Threats to validity

1. Small provider count: three providers, one benchmark architecture.
2. Synthetic corpus: 60 hidden queries; temporal rests on 36 queries per
   provider, authority on 6, provenance on 3.
3. Single common reader (`deepseek-v4-flash`). Unassisted scores are lower
   bounds on what a stronger reader could do with raw product text.
4. Adapter representation choices set the product/adapter boundary. A
   different adapter could move cells in the capability matrix.
5. Metadata and instruction interact; authority effects are partly
   substitutable, so per-channel attribution is not additive.
6. Multiple comparisons handled with Holm correction within property
   families; provenance remains underpowered by design.
7. Native/configuration ambiguity is reported (Hindsight requires
   application-supplied `query_timestamp`; Mem0 requires `user_id`), not
   manufactured into failures.
8. Absence of a native capability is recorded as UNSUPPORTED, not as failure;
   application-level extensibility is not treated as product capability.
9. No independent reproduction by a second lab yet.
10. The protocol directory hash changed after preregistration because
    `deviations.md` joined the directory; preregistration content is
    unchanged.

## Errata trail

### Capability Attribution Ablation v1 deviation

Recorded in `protocols/capability-attribution-v1/deviations.md` before the
restarted TEST run:

- The first GBrain TEST pack was interrupted at the user's request.
- The abandoned pack is preserved at
  `runs/followups/capability-attribution-v1/test/gbrain/pack-1-interrupted-20260807T125245`
  with a recorded directory digest
  (`9E2123BA59776F34AE252989BD701EC28D89C8C0C326D5220E829C105DF9FC0E`).
- Two abandoned DeepSeek calls (1,682 input / 1,711 output tokens, USD
  0.000715) remain in the GBrain ledger and in total cost; they are excluded
  from analysis.
- No hidden response outcome was inspected before the rerun decision.
- The rerun used the frozen implementation unchanged.

### Prior corrected research (unchanged, authoritative)

- Frozen Task 15: `c3007f4`
- `docs/reports/semantic-memory-exit-v1-errata.md`
- `docs/reports/semantic-memory-exit-v1-corrected.md`

This experiment neither modifies nor recomputes those records.
