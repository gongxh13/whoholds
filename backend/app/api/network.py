from __future__ import annotations

from fastapi import APIRouter

from app.models import NetworkResponse, NetworkStats

router = APIRouter(tags=["network"])


@router.get("/network", response_model=NetworkResponse)
def network(focus: str, hops: int = 1, min_pct: float = 0.0) -> NetworkResponse:
    # TODO(PR 5): port ego-network expansion from assets/v2-prototype.py:342.
    return NetworkResponse(
        focus=focus,
        nodes=[],
        edges=[],
        stats=NetworkStats(n_nodes=0, n_edges=0, truncated=False),
    )
