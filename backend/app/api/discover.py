from __future__ import annotations

from fastapi import APIRouter

from app.db.connection import connect
from app.models import CoholderPair, CrossHolder
from app.models.discover import CrossHolderCompany

router = APIRouter(prefix="/discover", tags=["discover"])


@router.get("/top-cross-holders", response_model=list[CrossHolder])
def top_cross_holders(limit: int = 20) -> list[CrossHolder]:
    """High-frequency cross-company individual shareholders.

    Source: `holder_companies` (whole-market coverage from teamwork ETL).
    `total_value` is enriched from holdings × latest close when available.
    """
    out: list[CrossHolder] = []
    try:
        with connect("entities") as conn:
            rows = conn.execute(
                """
                SELECT holder_name,
                       COUNT(DISTINCT stock_code) AS n_companies
                FROM holder_companies
                WHERE holder_type = '个人'
                GROUP BY holder_name
                ORDER BY n_companies DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            holders = [(r["holder_name"], r["n_companies"]) for r in rows]
            companies_by_holder: dict[str, list[CrossHolderCompany]] = {}
            for name, _ in holders:
                comp_rows = conn.execute(
                    """
                    SELECT stock_code, stock_name FROM holder_companies
                    WHERE holder_name = ? LIMIT 25
                    """,
                    (name,),
                ).fetchall()
                companies_by_holder[name] = [
                    CrossHolderCompany(
                        stock_code=r["stock_code"],
                        stock_name=r["stock_name"],
                        pct_total=None,
                        holdings=0,
                    )
                    for r in comp_rows
                ]
    except Exception:
        return []
    for name, n in holders:
        total_value = _enrich_total_value(name)
        out.append(
            CrossHolder(
                holder_name=name,
                n_companies=n,
                companies=companies_by_holder.get(name, []),
                total_value=total_value,
            )
        )
    return out


@router.get("/top-coholder-pairs", response_model=list[CoholderPair])
def top_coholder_pairs(limit: int = 50, min_co: int = 3) -> list[CoholderPair]:
    try:
        with connect("entities") as conn:
            rows = conn.execute(
                """
                SELECT holder_a, holder_b, co_count, company_list
                FROM coholder_pairs
                WHERE co_count >= ? AND holder_a < holder_b
                  AND holder_a_type = '个人' AND holder_b_type = '个人'
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


def _enrich_total_value(name: str) -> float | None:
    """Best-effort SUM(holdings × close) from holdings.db + prices.db.

    Falls back to None when either DB is missing or the holder has no detailed
    rows in `top10_holders` (i.e. teamwork-only).
    """
    try:
        with connect("holdings") as hconn:
            rows = hconn.execute(
                """
                SELECT t.stock_code, t.holdings, t.report_date
                FROM top10_holders t
                WHERE t.holder_name = ?
                  AND t.report_date = (
                      SELECT MAX(report_date) FROM top10_holders
                      WHERE holder_name = ? AND stock_code = t.stock_code
                  )
                """,
                (name, name),
            ).fetchall()
    except Exception:
        return None
    if not rows:
        return None
    total = 0.0
    found = False
    try:
        with connect("prices") as pconn:
            for r in rows:
                price = pconn.execute(
                    """
                    SELECT close FROM stock_daily_price
                    WHERE stock_code = ? AND adjust = '' AND date <= ?
                    ORDER BY date DESC LIMIT 1
                    """,
                    (r["stock_code"], r["report_date"]),
                ).fetchone()
                if price and price["close"]:
                    total += r["holdings"] * price["close"]
                    found = True
    except Exception:
        return None
    return total if found else None
