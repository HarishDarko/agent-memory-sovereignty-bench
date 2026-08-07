# Hindsight API server image (pinned commit, local offline stack).
# Built at the Phase 1 environment gate: pulls the torch stack for local
# embeddings/rerankers. MIT licensed.
FROM python:3.12-slim
WORKDIR /opt/hindsight
ARG HINDSIGHT_COMMIT=797faf7981ce9332e2ce7c922471b72b506b4065
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir "hindsight-api @ git+https://github.com/vectorize-io/hindsight@${HINDSIGHT_COMMIT}#subdirectory=hindsight-api"
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["hindsight-api"]
