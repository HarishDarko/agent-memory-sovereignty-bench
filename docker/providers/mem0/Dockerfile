# Mem0 OSS provider image: pinned upstream commit + local (offline) runtime.
# The embedding model is downloaded at build time so runtime is fully offline.
FROM python:3.12-slim
WORKDIR /opt/mem0
ARG MEM0_COMMIT=3f39fba28f7781aaf581f64a4af39d017af65835
RUN pip install --no-cache-dir "mem0ai[vector-stores] @ git+https://github.com/mem0ai/mem0@${MEM0_COMMIT}" \
    && pip install --no-cache-dir fastembed \
    && python -c "from fastembed import TextEmbedding; TextEmbedding(model_name='BAAI/bge-small-en-v1.5')"
WORKDIR /app
COPY benchmark /app/benchmark
COPY providers /app/providers
COPY config /app/config
ENV MEM0_TELEMETRY=false PYTHONUNBUFFERED=1
CMD ["python", "-c", "import time; time.sleep(3600)"]
