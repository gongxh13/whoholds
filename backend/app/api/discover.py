from __future__ import annotations

from fastapi import APIRouter

from app.db.connection import connect
from app.models import CoholderPair, CrossHolder

router = APIRouter(prefix="/discover", tags=["discover"])


@router.get("/top-cross-holders", response_model=list[CrossHolder])
def top_cross_holders(limit: int = 20) -> list[CrossHolder]:
    # TODO(PR 5): port total_value + per-holder company list from prototype:428.
    return []


@router.get("/top-coholder-pairs", response_model=list[CoholderPair])
def top_coholder_pairs(limit: int = 50, min_co: int = 3) -> list[CoholderPair]:
    try:
        with connect("entities") as conn:
            rows = conn.execute(
                """
                SELECT holder_a, holder_b, co_count, company_list
                FROM coholder_pairs
                WHERE co_count >= ? AND holder_a < holder_b
                ORDER BY co_count DESC
                LIMIT ?
                """,
                (min_co, limit),
            ).fetchall()
            return [
                CoholderPair(
                    holder_a=r["holder_a"],
                    holder_b=r["holder_b"],
                    co_count=r["co_count"],
                    company_list=r["company_list"] or "",
                )
                for r in rows
            ]
    except Exception:
        return []
