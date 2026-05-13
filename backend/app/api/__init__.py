"""FastAPI routers — one module per sub-domain.

PR 1 ships the route surface + Pydantic models so the OpenAPI schema is stable
and the frontend can codegen against it. Endpoint bodies will be filled in
through PR 3–5 (UI migration) and PR 7–8 (ETL + disambiguation).
"""
from fastapi import APIRouter

from app.api import company, discover, health, network, person, search

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(search.router)
api_router.include_router(person.router)
api_router.include_router(company.router)
api_router.include_router(network.router)
api_router.include_router(discover.router)
