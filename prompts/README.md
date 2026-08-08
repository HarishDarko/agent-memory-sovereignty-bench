# Prompts

Reader prompts are versioned. `reader-v1.md` is the fixed reader system prompt
for Phase 0 and Phase 1 controlled runs.

The prompt hash recorded in every run manifest is the SHA-256 of the prompt file
bytes concatenated with the prompt version string, so prompt changes are always
detectable in run provenance.

AMSB is reader-provider neutral: the prompt is one part of the reader
configuration, and the reader is independent of memory-provider adapters.
DeepSeek V4 Flash is the frozen reference reader for exact reproduction of
the AMSB Protocol v1 model-backed results; other reader configurations are
valid for new experiments but constitute a different experimental
configuration.

Never put answers, gold data, or benchmark secrets in a prompt file.
