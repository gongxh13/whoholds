"""Pull top-10 (total) and top-10-free shareholders for a (stock, report_date).

The data lives in AKShare's `stock_gdfx_top_10_em` and `stock_gdfx_free_top_10_em`
endpoints (Eastmoney data.eastmoney.com source — *not* push2his, that subdomain
is GFW-flaky, see design.md §抓取细节).

Function shape: `pull_one(stock_code, report_date)` does one snapshot, with
tenacity retry. `pull_market(...)` orchestrates the whole-market loop with
async limiter + per-snapshot etl_progress tracking.
"""
from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from datetime import date

from tenacity import retry, stop_after_attempt, wait_exponential

from app.etl.common import (
    JobStatus,
    alert,
    already_succeeded,
    dead_letter,
    record_progress,
    write_db,
)

JOB = "pull_top10"

# Eastmoney column names (Chinese) → our schema columns.
_TOTAL_MAP = {
    "股票代码": "stock_code",
    "股票简称": "stock_name",
    "报告期": "report_date",
    "名次": "rank",
    "股东名称": "holder_name",
    "股份类型": "share_type",
    "持股数": "holdings",
    "占总股本持股比例": "pct_total",
    "增减": "change_value",
    "增减比例": "change_pct",
}
_FREE_MAP = {
    "股票代码": "stock_code",
    "股票简称": "stock_name",
    "报告期": "report_date",
    "名次": "rank",
    "股东名称": "holder_name",
    "股东性质": "holder_nature",
    "股份类型": "share_type",
    "持股数": "holdings",
    "占总流通股本持股比例": "pct_free",
    "增减": "change_value",
    "增减比例": "change_pct",
}


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
def _fetch_total(stock_code: str, report_date: str):
    import akshare as ak

    return ak.stock_gdfx_top_10_em(symbol=stock_code, date=report_date)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
def _fetch_free(stock_code: str, report_date: str):
    import akshare as ak

    return ak.stock_gdfx_free_top_10_em(symbol=stock_code, date=report_date)


def pull_one(stock_code: str, report_date: str, *, force: bool = False) -> JobStatus:
    """Pull one (stock, date) snapshot into both top10_holders and top10_free_holders."""
    key = f"{stock_code}:{report_date}"
    if not force and already_succeeded(JOB, key):
        return JobStatus(JOB, key, "skipped")

    try:
        total_df = _fetch_total(stock_code, report_date)
        free_df = _fetch_free(stock_code, report_date)
    except Exception as exc:  # noqa: BLE001
        dead_letter(JOB, key, "", str(exc))
        status = JobStatus(JOB, key, "error", str(exc))
        record_progress(status)
        return status

    conn = write_db("holdings")
    try:
        _upsert(conn, "top10_holders", total_df, _TOTAL_MAP, stock_code, report_date)
        _upsert(
            conn, "top10_free_holders", free_df, _FREE_MAP, stock_code, report_date
        )
        conn.commit()
    finally:
        conn.close()

    status = JobStatus(JOB, key, "ok")
    record_progress(status)
    return status


def _upsert(
    conn: sqlite3.Connection,
    table: str,
    df,
    col_map: dict[str, str],
    stock_code: str,
    report_date: str,
) -> None:
    if df is None or len(df) == 0:
        return
    cols = [col_map[c] for c in df.columns if c in col_map]
    placeholders = ",".join("?" * len(cols))
    conn.execute(
        f"DELETE FROM {table} WHERE stock_code = ? AND report_date = ?",
        (stock_code, report_date),
    )
    rows = []
    for _, r in df.iterrows():
        row = []
        for chinese, key in col_map.items():
            if chinese not in df.columns:
                continue
            val = r[chinese]
            if key == "stock_code":
                val = stock_code  # ensure prefixed form
            if key == "report_date":
                val = str(val).replace("-", "")[:8]
            if key in ("holdings", "rank") and val is not None:
                try:
                    val = int(val)
                except (ValueError, TypeError):
                    val = None
            if key in ("pct_total", "pct_free", "change_pct") and val is not None:
                try:
                    val = float(val)
                except (ValueError, TypeError):
                    val = None
            row.append(val)
        rows.append(row)
    if rows:
        conn.executemany(
            f"INSERT OR REPLACE INTO {table} ({','.join(cols)}) VALUES ({placeholders})",
            rows,
        )


def quarter_ends(start_year: int = 2005, end_year: int | None = None) -> list[str]:
    """A-share standard reporting dates: 0331/0630/0930/1231 from start_year onward.

    Excludes quarters that haven't ended yet — Eastmoney returns nothing for
    future report dates and tenacity then burns three retries on each call.
    """
    today = date.today()
    if end_year is None:
        end_year = today.year
    out: list[str] = []
    for y in range(start_year, end_year + 1):
        for m, d in ((3, 31), (6, 30), (9, 30), (12, 31)):
            qd = date(y, m, d)
            if qd > today:
                continue
            out.append(f"{y}{m:02d}{d:02d}")
    return out


def pull_market(stock_codes: Iterable[str], dates: Iterable[str]) -> int:
    """Pull all (code, date) pairs serially — caller can wrap in asyncio for fanout."""
    n_ok = 0
    for code in stock_codes:
        for d in dates:
            try:
                if pull_one(code, d).status == "ok":
                    n_ok += 1
            except Exception as exc:  # noqa: BLE001
                alert("warn", JOB, f"{code}@{d}: {exc}")
    return n_ok
