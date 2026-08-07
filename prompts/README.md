# Prompts

Reader prompts are versioned. `reader-v1.md` is the fixed reader system prompt
for Phase 0 and Phase 1 controlled runs.

The prompt hash recorded in every run manifest is the SHA-256 of the prompt file
bytes concatenated with the prompt version string, so prompt changes are always
detectable in run provenance.

Never put answers, gold data, or benchmark secrets in a prompt file.
