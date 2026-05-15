#!/usr/bin/env sh
# Container startup:
#   1. Run schema migration (idempotent, cheap).
#   2. exec uvicorn (with APScheduler — daily/quarterly cron jobs).
#
# Real-data bootstrap is *never* auto: 6h + needs network, run manually:
#   docker compose exec backend python -m app.etl.bootstrap
set -eu

echo "[entrypoint] migrate"
python /app/scripts/migrate.py

echo "[entrypoint] starting uvicorn"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
