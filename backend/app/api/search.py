from __future__ import annotations

from fastapi import APIRouter, Query

from app.db.connection import connect
from app.models import SearchCompany, SearchPerson, SearchResponse

router = APIRouter(tags=["search"])


@router.get("/search", response_model=SearchResponse)
def search(q: str = Query(..., min_length=1)) -> SearchResponse:
    """Search across both holdings (top10) and entities (holder_companies).

    Companies hit either source (holdings has detailed timeline, holder_companies
    has whole-market teamwork coverage). People come from holder_companies only,
    since that's where we have the cleaner is_person='个人' filter.
    """
    like = f"%{q}%"
    companies: list[SearchCompany] = []
    seen_codes: set[str] = set()

    try:
        with connect("holdings") as conn:
            for r in conn.execute(
                """
                SELECT DISTINCT stock_code, stock_name FROM top10_holders
                WHERE stock_name LIKE ? OR stock_code LIKE ?
                LIMIT 20
                """,
                (like, like),
            ):
                if r["stock_code"] in seen_codes:
                    continue
                seen_codes.add(r["stock_code"])
                companies.append(
                    SearchCompany(stock_code=r["stock_code"], stock_name=r["stock_name"])
                )
    except Exception:
        pass

    try:
        with connect("entities") as conn:
            for r in conn.execute(
                """
                SELECT DISTINCT stock_code, stock_name FROM holder_companies
                WHERE stock_name LIKE ? OR stock_code LIKE ?
                LIMIT 20
                """,
                (like, like),
            ):
                if r["stock_code"] in seen_codes:
                    continue
                seen_codes.add(r["stock_code"])
                companies.append(
                    SearchCompany(stock_code=r["stock_code"], stock_name=r["stock_name"])
                )
    except Exception:
        pass

    people: list[SearchPerson] = []
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
            people = [
                SearchPerson(name=r["holder_name"], n_companies=r["n"]) for r in rows
            ]
    except Exception:
        pass

    return SearchResponse(people=people, companies=companies[:20])
