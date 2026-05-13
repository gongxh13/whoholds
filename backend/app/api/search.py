from __future__ import annotations

from fastapi import APIRouter, Query

from app.db.connection import connect
from app.models import SearchCompany, SearchPerson, SearchResponse

router = APIRouter(tags=["search"])


@router.get("/search", response_model=SearchResponse)
def search(q: str = Query(..., min_length=1)) -> SearchResponse:
    like = f"%{q}%"
    people: list[SearchPerson] = []
    companies: list[SearchCompany] = []

    try:
        with connect("holdings") as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT stock_code, stock_name
                FROM top10_holders
                WHERE stock_code LIKE ? OR stock_name LIKE ?
                LIMIT 20
                """,
                (like, like),
            ).fetchall()
            companies = [SearchCompany(stock_code=r["stock_code"], stock_name=r["stock_name"]) for r in rows]
    except Exception:
        # DB not yet migrated or empty — return empty results rather than 500.
        pass

    try:
        with connect("entities") as conn:
            rows = conn.execute(
                """
                SELECT holder_name, COUNT(DISTINCT stock_code) AS n
                FROM holder_companies
                WHERE holder_name LIKE ? AND holder_type = '个人'
                GROUP BY holder_name
                ORDER BY n DESC
                LIMIT 20
                """,
                (like,),
            ).fetchall()
            people = [SearchPerson(name=r["holder_name"], n_companies=r["n"]) for r in rows]
    except Exception:
        pass

    return SearchResponse(people=people, companies=companies)
