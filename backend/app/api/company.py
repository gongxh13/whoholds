from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.db.connection import connect
from app.models import CompanyDetail

router = APIRouter(tags=["company"])


@router.get("/company/{code}", response_model=CompanyDetail)
def company_detail(code: str, date: str | None = None) -> CompanyDetail:
    try:
        with connect("holdings") as conn:
            row = conn.execute(
                "SELECT stock_name FROM top10_holders WHERE stock_code = ? LIMIT 1",
                (code,),
            ).fetchone()
            if not row:
                raise HTTPException(status_code=404, detail=f"unknown stock_code: {code}")
            stock_name = row["stock_name"]

            dates = [
                r["report_date"]
                for r in conn.execute(
                    "SELECT DISTINCT report_date FROM top10_holders WHERE stock_code = ? ORDER BY report_date DESC",
                    (code,),
                ).fetchall()
            ]
    except HTTPException:
        raise
    except Exception:
        # DB not yet migrated — bare 404 so the API contract stays consistent.
        raise HTTPException(status_code=404, detail=f"unknown stock_code: {code}") from None

    # TODO(PR 5): port full top10 + stack_series build from assets/v2-prototype.py:298.
    return CompanyDetail(
        stock_code=code,
        stock_name=stock_name,
        available_dates=dates,
        current_date=date or (dates[0] if dates else None),
        top10=[],
        stack_series=[],
    )
