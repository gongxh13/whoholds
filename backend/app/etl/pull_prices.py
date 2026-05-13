"""Pull daily K-line for a stock — non-adjusted + qfq, both stored.

Per design.md §行情数据采坑, *must* use AKShare's `stock_zh_a_hist_tx` (Tencent
source) — the default `stock_zh_a_hist` hits push2his.eastmoney.com which is
GFW-flaky on Chinese networks.

Output schema: prices.stock_daily_price (stock_code, date, adjust, OHLC).
"""
from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterable

from tenacity import retry, stop_after_attempt, wait_exponential

from app.etl.common import (
    JobStatus,
    alert,
    already_succeeded,
    dead_letter,
    record_progress,
    write_db,
)

JOB = "pull_prices"


def _no_proxy() -> None:
    """push2his.eastmoney.com hates proxies — strip them once per process."""
    for k in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"):
        os.environ.pop(k, None)
    os.environ.setdefault("NO_PROXY", "*")


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
def _fetch(stock_code: str, start_date: str, end_date: str, adjust: str):
    import akshare as ak

    return ak.stock_zh_a_hist_tx(
        symbol=stock_code,
        start_date=start_date,
        end_date=end_date,
        adjust=adjust,
    )


def pull_one(
    stock_code: str,
    *,
    start_date: str = "20050101",
    end_date: str | None = None,
    force: bool = False,
) -> JobStatus:
    """Pull non-adjusted + qfq history for one stock."""
    end_date = end_date or _today()
    key = f"{stock_code}:{start_date}-{end_date}"
    if not force and already_succeeded(JOB, key):
        return JobStatus(JOB, key, "skipped")

    _no_proxy()
    try:
        dfs = {
            adjust: _fetch(stock_code, start_date, end_date, adjust)
            for adjust in ("", "qfq")
        }
    except Exception as exc:  # noqa: BLE001
        dead_letter(JOB, key, "", str(exc))
        status = JobStatus(JOB, key, "error", str(exc))
        record_progress(status)
        return status

    conn = write_db("prices")
    try:
        for adjust, df in dfs.items():
            _upsert(conn, stock_code, adjust, df)
        conn.commit()
    finally:
        conn.close()

    status = JobStatus(JOB, key, "ok")
    record_progress(status)
    return status


def _upsert(conn: sqlite3.Connection, stock_code: str, adjust: str, df) -> None:
    if df is None or len(df) == 0:
        return
    import pandas as pd

    df = df[["date", "open", "close", "high", "low"]].copy()
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y%m%d")
    rows = [
        (stock_code, str(r["date"]), adjust, float(r["open"]) if r["open"] is not None else None,
         float(r["close"]) if r["close"] is not None else None,
         float(r["high"]) if r["high"] is not None else None,
         float(r["low"]) if r["low"] is not None else None)
        for _, r in df.iterrows()
    ]
    conn.executemany(
        """
        INSERT OR REPLACE INTO stock_daily_price
            (stock_code, date, adjust, open, close, high, low)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )


def pull_market(stock_codes: Iterable[str], **kwargs) -> int:
    n_ok = 0
    for code in stock_codes:
        try:
            if pull_one(code, **kwargs).status == "ok":
                n_ok += 1
        except Exception as exc:  # noqa: BLE001
            alert("warn", JOB, f"{code}: {exc}")
    return n_ok


def _today() -> str:
    from datetime import date

    return date.today().strftime("%Y%m%d")
