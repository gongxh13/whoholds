from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import api_router

app = FastAPI(
    title="whoholds backend",
    version="0.1.0",
    description="A-share top-10 shareholder network & timeline API.",
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
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(api_router)
