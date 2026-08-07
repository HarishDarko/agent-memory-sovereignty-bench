# Reviewer Checklist

Purpose: verify that Capability Attribution Ablation v1 is configured
reasonably, attributes capabilities correctly, and supports its conclusions.
Private gold is intentionally not included in this package.

## 1. Provider configurations

- [ ] GBrain pinned at `15b9863d...` / v0.42.73.2 with `--no-embedding`,
  PGLite, keyword search, and adapter-written Markdown/frontmatter. Is this
  the configuration the research claims?
- [ ] Mem0 pinned at `3f39fba...` / v2.0.17 with `infer=False`, local Chroma,
  FastEmbed, telemetry disabled.
- [ ] Hindsight pinned at `797faf7...` / v0.8.6 with LLM features off and one
  isolated bank per pack.

Configurations are recorded in `docs/review/provider-configs/`.

## 2. Product vs adapter attribution

- [ ] Does the capability matrix separate what the product stores/enforces
  from what the adapter supplies (event catalog, authority/source labels,
  eligibility metadata)?
- [ ] Is adapter-added metadata never presented as product-native state?

## 3. Interface correctness

- [ ] GBrain CLI search used with the pinned binary and stopword handling
  (`benchmark/capability_provider_views.py`).
- [ ] Mem0 `search` used with its required `user_id` filter and local
  embeddings; hybrid scoring correctly disabled for Chroma.
- [ ] Hindsight recall used with the application-supplied `query_timestamp`;
  temporal ablation correctly labeled descriptive for Hindsight.

## 4. Ablation isolation

- [ ] Do the paired conditions differ only in the declared layer (metadata,
  prompt, or post-filter)?
- [ ] Identical item order, text, scores, token budget, reader, temperature,
  seed, and replicate count across cells?
- [ ] One raw retrieval call per query, with pre/post state-hash equality
  (mutation failures: 0)?

## 5. Statistics

- [ ] Pairing unit is provider/pack/query/replicate; exact McNemar on first
  attempt per query; block bootstrap by `pack:subject`; Holm within property
  family.
- [ ] Materiality rule applied exactly as preregistered, including the
  security-count exception for leakage transitions.
- [ ] Reader errors retained in denominators (8 of 918 attempts).

## 6. Conclusions bounded by evidence

- [ ] Claims limited to tested providers, pins, corpus, prompts, and reader.
- [ ] No aggregate governance score, no provider ranking, no "first" claims.
- [ ] Authority and provenance marked directional/underpowered where the
  strict gate is not met.

## 7. Reproducibility

- [ ] Preregistration commit (`4749319`) predates the TEST run code commit
  (`97f1f8`).
- [ ] Run manifests, manifest hashes, ledger hashes, and dataset commitment
  hashes verified by `scripts/analyze_capability_attribution.py`.
- [ ] Commands in `docs/reports/capability-attribution-v1.md` section 22
  reproduce the runs in a clean environment with
  `SOVBENCH_DEEPSEEK_API_KEY` set.
- [ ] The interrupted-run deviation and preservation hashes are recorded in
  `protocols/capability-attribution-v1/deviations.md`.

## Sign-off

Reviewer: ____________________  Date: ____________________

Findings:
