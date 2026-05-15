from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start the APScheduler only when explicitly enabled.

    Default is **off**: GitHub Actions (see weekly-refresh.yml) is the data
    authority — local scheduler running on consumer machines would diverge from
    the release snapshot and cause confusing inconsistencies.

    To run a local ETL pipeline anyway (e.g. development, air-gapped fork), set
    `WHOHOLDS_ENABLE_SCHEDULER=1`. The legacy `WHOHOLDS_DISABLE_SCHEDULER=1`
    still forces it off (wins over enable) — kept so existing tests / CI
    invocations don't break.
    """
    force_off = os.environ.get("WHOHOLDS_DISABLE_SCHEDULER") == "1"
    explicit_on = os.environ.get("WHOHOLDS_ENABLE_SCHEDULER") == "1"

    if explicit_on and not force_off:
        try:
            from app.etl.scheduler import build_scheduler

            scheduler = build_scheduler()
            scheduler.start()
            app.state.scheduler = scheduler
        except Exception:
            app.state.scheduler = None
    else:
        app.state.scheduler = None
    yield
    if getattr(app.state, "scheduler", None) is not None:
        app.state.scheduler.shutdown(wait=False)


app = FastAPI(
    title="whoholds backend",
    version="0.1.0",
    description="A-share top-10 shareholder network & timeline API.",
    lifespan=lifespan,
)

# Dev only — Caddy basic-auth fronting in prod (see PR 11).
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:5174",
        "http://localhost:5174",
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(api_router)
