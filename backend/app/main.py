from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start the APScheduler unless WHOHOLDS_DISABLE_SCHEDULER is set.

    Tests and the dev server typically set the env-var to skip the scheduler;
    production (PR 11 docker compose) leaves it enabled.
    """
    if os.environ.get("WHOHOLDS_DISABLE_SCHEDULER") != "1":
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
