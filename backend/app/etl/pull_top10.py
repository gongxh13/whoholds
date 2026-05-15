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
import threading
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
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

_write_lock = threading.Lock()

JOB = "pull_top10"

# Eastmoney column names (Chinese) → our schema columns.
# NOTE: stock_code / stock_name / report_date are *not* in the dataframe —
# they're inputs to the API call. _upsert injects them from function args.
# change_pct is `变动比率` in the actual response (not `增减比例` as some docs say).
_TOTAL_MAP = {
    "名次": "rank",
    "股东名称": "holder_name",
    "股份类型": "share_type",
    "持股数": "holdings",
    "占总股本持股比例": "pct_total",
    "增减": "change_value",
    "变动比率": "change_pct",
}
_FREE_MAP = {
    "名次": "rank",
    "股东名称": "holder_name",
    "股东性质": "holder_nature",
    "股份类型": "share_type",
    "持股数": "holdings",
    "占总流通股本持股比例": "pct_free",
    "增减": "change_value",
    "变动比率": "change_pct",
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
        with _write_lock:
            dead_letter(JOB, key, "", str(exc))
            status = JobStatus(JOB, key, "error", str(exc))
            record_progress(status)
        return status

    stock_name = _stock_name_for(stock_code)

    with _write_lock:
        conn = write_db("holdings")
        try:
            _upsert(conn, "top10_holders", total_df, _TOTAL_MAP,
                    stock_code, stock_name, report_date)
            _upsert(conn, "top10_free_holders", free_df, _FREE_MAP,
                    stock_code, stock_name, report_date)
            conn.commit()
        finally:
            conn.close()
        status = JobStatus(JOB, key, "ok")
        record_progress(status)
    return status


def _stock_name_for(stock_code: str) -> str:
    """Resolve a stock_code to its Chinese name from entities.holder_companies."""
    from app.db.connection import connect

    try:
        with connect("entities") as conn:
            row = conn.execute(
                "SELECT stock_name FROM holder_companies WHERE stock_code = ? LIMIT 1",
                (stock_code,),
            ).fetchone()
            if row and row["stock_name"]:
                return row["stock_name"]
    except Exception:  # noqa: BLE001
        pass
    return stock_code  # fall back to the code itself rather than NULL


def _upsert(
    conn: sqlite3.Connection,
    table: str,
    df,
    col_map: dict[str, str],
    stock_code: str,
    stock_name: str,
    report_date: str,
) -> None:
    if df is None or len(df) == 0:
        return
    # Eastmoney's response columns are just the table body; stock_code /
    # stock_name / report_date come from the API call inputs. Inject them
    # explicitly so they never end up NULL, regardless of column order.
    df_cols = [(chinese, col_map[chinese]) for chinese in df.columns if chinese in col_map]
    cols = ["stock_code", "stock_name", "report_date"] + [key for _, key in df_cols]
    placeholders = ",".join("?" * len(cols))
    conn.execute(
        f"DELETE FROM {table} WHERE stock_code = ? AND report_date = ?",
        (stock_code, report_date),
    )
    rows = []
    for _, r in df.iterrows():
        # Leading three: from function args; rest: from df in df.columns order.
        row: list = [stock_code, stock_name, report_date]
        for chinese, key in df_cols:
            val = r[chinese]
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


def pull_market(
    stock_codes: Iterable[str],
    dates: Iterable[str],
    *,
    concurrency: int = 6,
) -> int:
    """Pull all (code, date) pairs in parallel (default 6 workers)."""
    pairs = [(c, d) for c in stock_codes for d in dates]
    if concurrency <= 1:
        n_ok = 0
        for code, d in pairs:
            try:
                if pull_one(code, d).status == "ok":
                    n_ok += 1
            except Exception as exc:  # noqa: BLE001
                alert("warn", JOB, f"{code}@{d}: {exc}")
        return n_ok

    n_ok = 0
    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        futs = {ex.submit(pull_one, c, d): (c, d) for c, d in pairs}
        for fut in as_completed(futs):
            c, d = futs[fut]
            try:
                if fut.result().status == "ok":
                    n_ok += 1
            except Exception as exc:  # noqa: BLE001
                alert("warn", JOB, f"{c}@{d}: {exc}")
    return n_ok
