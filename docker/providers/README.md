# Provider images (Phase 1+)

One directory per provider under `docker/providers/` will hold its Dockerfile,
healthcheck, and configuration for the clean-room pattern in
`docker/compose.yml`. Phase 0 uses only in-process baselines, so no images
exist yet.

Conventions for every provider image:
- Store all state under `/provider-state` (its own named volume).
- Reach the reader model only via `DEEPSEEK_BASE_URL` (the gateway).
- No hardcoded API keys; keys come from the gateway, not the provider.
- Do not install or expose web search / browsing / cloud client SDKs unless the
  provider's design requires them (then record it as an operational
  characteristic).
