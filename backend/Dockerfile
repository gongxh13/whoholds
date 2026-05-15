# whoholds backend — FastAPI + uvicorn + APScheduler.
# Multi-stage so the runtime image doesn't carry uv or the build toolchain.
FROM python:3.12-slim AS builder
WORKDIR /app

ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_PYTHON_DOWNLOADS=never \
    UV_LINK_MODE=copy

# uv is the only build-time tool we need (matches AGENTS.md).
RUN pip install --no-cache-dir uv==0.4.30

COPY pyproject.toml uv.lock ./
# ETL extras (akshare + pandas) are needed for app.etl.bootstrap inside the
# container; without them the auto-scheduled jobs can't actually fetch data.
RUN uv sync --frozen --no-dev --extra etl

COPY app ./app
COPY scripts ./scripts
COPY entrypoint.sh ./entrypoint.sh
RUN chmod +x ./entrypoint.sh

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
ENTRYPOINT ["./entrypoint.sh"]
