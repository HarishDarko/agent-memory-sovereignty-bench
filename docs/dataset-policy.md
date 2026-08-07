# Dataset Policy

## Classes

| Class | Status |
|---|---|
| DEV corpus (`datasets/dev/personal/`) | public: events, queries, ground truth, dataset card |
| Example corpora (`datasets/followups/semantic-exit-v1/`) | public |
| TEST inputs | not released; hidden packs exist only as commitment hashes |
| Hidden gold (`scorer_private/`) | private; never mounted into providers or readers |
| Commitments (`datasets/commitments/`) | public SHA-256 hashes proving the hidden packs existed before execution |

## Rules

- Gold answers, acceptable aliases, and evidence IDs are never written into
  provider state, provider containers, or reader prompts.
- The private test split and gold are gitignored until the benchmark results
  are frozen and released; AMSB ships the commitments only.
- Public corpora are synthetic; no real personal or project data.

## Regeneration

- `scripts/generate_dev_corpus.py` regenerates the public DEV corpus.
- `scripts/generate_hidden_test.py` generates the hidden packs and commits
  only their commitments; it never overwrites existing packs without
  `--force` (which breaks commitment integrity).
- `scripts/generate_private_test.py` is intentionally a stub until a release
  decision is made.
