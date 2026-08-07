# Changelog

## 1.0.0 (2026-08-07)

Initial open-source release of AMSB, curated from the research repository
`memory-sovereignty-bench` (source HEAD `bee627b`).

### Added

- Fresh Git history and AMSB packaging (`pyproject.toml`, `uv.lock`)
- Registry-driven provider boundary (`providers/registry.py`,
  `providers/registry.json`) with exact researched pins
- Per-provider capability manifests (`providers/<name>/manifest.toml`)
- Contributor validation command (`scripts/validate_provider.py`)
- Provider template (`templates/provider/`)
- Public documentation set (`docs/`), including the mandatory
  `docs/adding-a-provider.md` tutorial
- Community files: LICENSE (Apache-2.0), CONTRIBUTING, SECURITY,
  CODE_OF_CONDUCT, CITATION.cff, THIRD_PARTY_NOTICES
- Published research artifacts under `reports/` (frozen V1 tables,
  capability-attribution analysis and manifests, cost ledger)
- Scientific audit documentation (`docs/scientific-audit.md`)

### Changed

- Machine-specific paths sanitized to `%USERPROFILE%` / `Path.home()` forms
- Provider construction switched to the registry factory (behavior and
  pins unchanged)

### Preserved

- Frozen research reports and errata trail (`docs/reports/`,
  `docs/research-history/`)
- Exact provider pins and controlled configurations
- Full unit/contract/integration test suite
