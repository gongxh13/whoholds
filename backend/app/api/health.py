from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.config import DB_PATHS

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    databases: dict[str, bool]


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        databases={name: path.exists() for name, path in DB_PATHS.items()},
    )
