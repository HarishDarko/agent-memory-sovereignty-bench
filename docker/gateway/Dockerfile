# Policy-gated model gateway proxy (Task 3). Built and pulled only when a real
# provider run needs it; the local integration tests run the proxy directly
# without this image.
FROM python:3.12-slim
WORKDIR /app
COPY benchmark /app/benchmark
COPY config /app/config
COPY docker/gateway/entrypoint.py /app/entrypoint.py
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["python", "/app/entrypoint.py"]
