# GBrain provider image: pinned upstream commit + this repo's adapter.
# MIT licensed; built at a pinned commit for local benchmark use.
FROM oven/bun:1.3.10-slim
WORKDIR /opt/gbrain
ARG GBRAIN_COMMIT=15b9863d13635d173562a54f55a1d388bfcf546b
RUN git clone https://github.com/garrytan/gbrain.git . \
    && git checkout ${GBRAIN_COMMIT} \
    && bun install --frozen-lockfile \
    && bun link \
    && rm -rf .git admin test tests
WORKDIR /app
COPY benchmark /app/benchmark
COPY providers /app/providers
COPY config /app/config
ENV GBRAIN_BIN=/opt/gbrain/src/cli.ts PYTHONUNBUFFERED=1
CMD ["bun", "run", "/opt/gbrain/src/cli.ts", "status"]
