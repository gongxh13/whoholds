# whoholds backend — FastAPI + uvicorn + APScheduler.
# Multi-stage so the runtime image doesn't carry uv or the build toolchain.
FROM python:3.12-slim AS builder
WORKDIR /app

# uv is the only build-time tool we need (matches AGENTS.md).
RUN pip install --no-cache-dir uv==0.4.30

COPY pyproject.toml uv.lock ./
RUN uv venv /opt/venv && uv sync --frozen --no-dev

COPY app ./app
COPY scripts ./scripts

FROM python:3.12-slim AS runtime
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    WHOHOLDS_DATA_DIR=/data

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /app /app

RUN useradd -u 10001 -m whoholds && \
    mkdir -p /data && chown -R whoholds /data /app
USER whoholds

EXPOSE 8000
HEALTHCHECK CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health').read()" || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
