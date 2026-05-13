from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.db.connection import connect
from app.models import CompanyDetail, StackSeriesPoint, Top10Row
from app.services.heuristics import is_person_heuristic

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
            current_date = date or (dates[0] if dates else None)

            top10: list[Top10Row] = []
            if current_date:
                top10 = _load_top10(conn, code, current_date)

            stack_series = _load_stack_series(conn, code)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=404, detail=f"unknown stock_code: {code}") from None

    return CompanyDetail(
        stock_code=code,
        stock_name=stock_name,
        available_dates=dates,
        current_date=current_date,
        top10=top10,
        stack_series=stack_series,
    )


def _load_top10(conn, code: str, date: str) -> list[Top10Row]:
    """Join total + free shareholder rows for the given (code, date) snapshot.

    Free-table provides `holder_nature` (the authoritative is_person signal);
    when a row only exists in the total table (限售流通股), nature stays None
    and we fall back to keyword heuristic.
    """
    rows = conn.execute(
        """
        SELECT t.rank, t.holder_name, t.share_type, t.holdings, t.pct_total,
               t.change_value, t.change_pct,
               fh.holder_nature, fh.pct_free
        FROM top10_holders t
        LEFT JOIN top10_free_holders fh
               ON t.stock_code = fh.stock_code
              AND t.report_date = fh.report_date
              AND t.holder_name = fh.holder_name
        WHERE t.stock_code = ? AND t.report_date = ?
        ORDER BY t.rank
        """,
        (code, date),
    ).fetchall()
    close_unadj = _close_on_or_before(conn, code, date)
    out: list[Top10Row] = []
    for r in rows:
        is_p = is_person_heuristic(r["holder_name"], r["holder_nature"])
        mv = (r["holdings"] * close_unadj) if (close_unadj and r["holdings"]) else None
        out.append(
            Top10Row(
                rank=r["rank"],
                holder_name=r["holder_name"],
                share_type=r["share_type"],
                holdings=r["holdings"],
                pct=r["pct_total"],
                pct_field="pct_total",
                change_value=r["change_value"],
                change_pct=r["change_pct"],
                is_person=is_p,
                source_table="top10_holders",
                holdings_value=mv,
            )
        )
    return out


def _load_stack_series(conn, code: str) -> list[StackSeriesPoint]:
    rows = conn.execute(
        """
        SELECT report_date, holder_name, holdings
        FROM top10_holders
        WHERE stock_code = ?
        ORDER BY report_date, rank
        """,
        (code,),
    ).fetchall()
    return [
        StackSeriesPoint(
            date=r["report_date"],
            holder_name=r["holder_name"],
            holdings=r["holdings"],
            holdings_value=None,
        )
        for r in rows
    ]


def _close_on_or_before(conn, code: str, date: str) -> float | None:
    """Last unadjusted close ≤ report_date — joins across the prices DB.

    The prices DB is a *separate* SQLite file, so we ATTACH it for the duration
    of one query. ATTACH on a read-only URI works because the holdings conn
    itself opened the prices file read-only via `mode=ro` would conflict —
    we instead just open a fresh connection to prices.db.
    """
    from app.db.connection import connect as _connect

    try:
        with _connect("prices") as pconn:
            row = pconn.execute(
                """
                SELECT close FROM stock_daily_price
                 WHERE stock_code = ? AND adjust = '' AND date <= ?
                 ORDER BY date DESC LIMIT 1
                """,
                (code, date),
            ).fetchone()
            return row["close"] if row else None
    except Exception:
        return None
