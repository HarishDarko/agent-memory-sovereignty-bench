# Security Policy

## Reporting a vulnerability

Do not open a public issue for security findings. Report privately to the
maintainers via a GitHub security advisory (once the repository is public)
or direct maintainer contact.

## What AMSB protects

- private hidden-TEST gold (`scorer_private/`) - never committed, mounted,
  or copied into provider runtimes
- API keys and credentials - environment variables only, never committed
- provider isolation - one provider per run, no cross-provider volumes or
  networks, no uncontrolled container egress
- benchmark integrity - deterministic clock, state-hash verification,
  fail-closed invariants

## Handling

Confirmed findings are fixed with an additive record (no history rewrite)
and disclosed after the fix ships. Research artifacts are preserved; fixes
are documented alongside them.
