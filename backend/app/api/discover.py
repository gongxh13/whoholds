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

    Implementation: 3 queries total (entities × 2 + holdings + prices),
    not (1 + N + N × M) — keep it under 500ms for limit=20.
    """
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
            if not holders:
                return []
            names = [n for n, _ in holders]
            placeholders = ",".join("?" * len(names))
            comp_rows = conn.execute(
                f"""
                SELECT holder_name, stock_code, stock_name
                FROM holder_companies
                WHERE holder_name IN ({placeholders})
                ORDER BY holder_name, stock_code
                """,
                names,
            ).fetchall()
    except Exception:
        return []

    companies_by_holder: dict[str, list[CrossHolderCompany]] = {n: [] for n in names}
    for r in comp_rows:
        bucket = companies_by_holder[r["holder_name"]]
        if len(bucket) >= 25:
            continue
        bucket.append(
            CrossHolderCompany(
                stock_code=r["stock_code"],
                stock_name=r["stock_name"],
                pct_total=None,
                holdings=0,
            )
        )

    total_value_by_holder = _enrich_total_values(names)
    return [
        CrossHolder(
            holder_name=name,
            n_companies=n,
            companies=companies_by_holder.get(name, []),
            total_value=total_value_by_holder.get(name),
        )
        for name, n in holders
    ]


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


def _enrich_total_values(names: list[str]) -> dict[str, float]:
    """Batch SUM(holdings × close) for many holders at once.

    Two queries: one into holdings (latest report per holder/stock), one into
    prices (latest close ≤ report_date). Python combines. O(holders + holdings)
    instead of O(holders × holdings) round trips.
    """
    if not names:
        return {}
    placeholders = ",".join("?" * len(names))
    try:
        with connect("holdings") as hconn:
            holding_rows = hconn.execute(
                f"""
                SELECT holder_name, stock_code, holdings, report_date
                FROM top10_holders t
                WHERE holder_name IN ({placeholders})
                  AND report_date = (
                      SELECT MAX(report_date) FROM top10_holders
                      WHERE holder_name = t.holder_name AND stock_code = t.stock_code
                  )
                """,
                names,
            ).fetchall()
    except Exception:
        return {}
    if not holding_rows:
        return {}

    # Group by (stock_code, report_date) so we only ask for each price once.
    distinct_keys = {(r["stock_code"], r["report_date"]) for r in holding_rows}
    price_lookup: dict[tuple[str, str], float] = {}
    try:
        with connect("prices") as pconn:
            stocks = sorted({sc for sc, _ in distinct_keys})
            stock_placeholders = ",".join("?" * len(stocks))
            # Pull *all* non-adjust prices for these stocks; pick the right
            # ≤report_date one in Python. Cheaper than N round-trips.
            rows = pconn.execute(
                f"""
                SELECT stock_code, date, close FROM stock_daily_price
                WHERE adjust = '' AND stock_code IN ({stock_placeholders})
                """,
                stocks,
            ).fetchall()
            by_stock: dict[str, list[tuple[str, float]]] = {}
            for r in rows:
                by_stock.setdefault(r["stock_code"], []).append(
                    (r["date"], r["close"])
                )
            for series in by_stock.values():
                series.sort()  # ascending date
            for stock_code, report_date in distinct_keys:
                series = by_stock.get(stock_code) or []
                last_close: float | None = None
                for d, c in series:
                    if d <= report_date and c:
                        last_close = c
                    elif d > report_date:
                        break
                if last_close is not None:
                    price_lookup[(stock_code, report_date)] = last_close
    except Exception:
        return {}

    totals: dict[str, float] = {}
    for r in holding_rows:
        close = price_lookup.get((r["stock_code"], r["report_date"]))
        if close is None:
            continue
        totals[r["holder_name"]] = totals.get(r["holder_name"], 0.0) + (
            r["holdings"] * close
        )
    return totals
