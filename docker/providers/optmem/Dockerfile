# OptMem provider image: pinned upstream commit + this repo's adapter.
# NOTE: OptMem has no license file (all rights reserved by default). The
# pinned script is fetched at build time for local use only and is never
# redistributed or vendored into this repository.
FROM python:3.12-slim
WORKDIR /opt/optmem
ARG OPTMEM_COMMIT=1fb164cf39028047781f72ac3bb1e5a691c1dcb0
RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && git clone https://github.com/VictorTaelin/OptMem.git . \
    && git checkout ${OPTMEM_COMMIT} \
    && rm -rf .git anim install.sh test.py \
    && chmod +x memo \
    && apt-get purge -y git \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY benchmark /app/benchmark
COPY providers /app/providers
COPY config /app/config
ENV OPTMEM_MEMO_PATH=/opt/optmem/memo PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["python", "-m", "providers.optmem.adapter"]
