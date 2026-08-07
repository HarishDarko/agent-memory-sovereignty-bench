# Limitations

- Three researched providers, one benchmark architecture, one synthetic
  corpus.
- A single common reader (`deepseek-v4-flash`); unassisted scores are lower
  bounds on what a stronger reader could do with raw product text.
- Adapter representation choices set the product/adapter boundary; a
  different adapter could shift attribution cells.
- Authority and provenance ablations rest on small query counts (6 and 3 per
  provider) and are directional, not statistically resolved.
- The assisted scope condition also applies temporal eligibility filtering;
  the scope delta bundles both effects (documented in `docs/scientific-audit.md`).
- No independent reproduction by a second lab yet.
- Hidden TEST gold and private run artifacts are unavailable to AMSB users;
  published commitments prove the packs existed but not their contents.
- No cross-provider migration was executed; portability conclusions are
  bounded to export/recovery evidence.
