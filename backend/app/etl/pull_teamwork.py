"""Pull eastmoney shareholder-cooperation data (`stock_gdfx_holding_teamwork_em`).

This is the project's "half-father" data source per design.md — gives a single
shot of the 1434-ish core individual shareholders' whole-market cross-company
appearances. Single call takes ~35min, so this is *not* a per-stock fanout —
it's one batch into a raw table, then `ingest_teamwork` expands it into
`holder_companies` + `coholder_pairs`.
"""
from __future__ import annotations

import sqlite3
import time

from tenacity import retry, stop_after_attempt, wait_exponential

from app.etl.common import JobStatus, dead_letter, record_progress, write_db

JOB = "pull_teamwork"


@retry(stop=stop_after_attempt(2), wait=wait_exponential(min=10, max=60))
def _fetch(symbol: str = "个人"):
    import akshare as ak

    return ak.stock_gdfx_holding_teamwork_em(symbol=symbol)


def pull_full(symbol: str = "个人") -> JobStatus:
    key = f"symbol={symbol}"
    t0 = time.time()
    try:
        df = _fetch(symbol)
    except Exception as exc:  # noqa: BLE001
        dead_letter(JOB, key, "", str(exc))
        status = JobStatus(JOB, key, "error", str(exc))
        record_progress(status)
        return status

    elapsed = time.time() - t0
    print(f"[teamwork] pulled {len(df)} rows in {elapsed:.0f}s", flush=True)

    conn = write_db("entities")
    try:
        _persist_raw(conn, df)
        conn.commit()
    finally:
        conn.close()

    status = JobStatus(JOB, key, "ok")
    record_progress(status)
    return status


def _persist_raw(conn: sqlite3.Connection, df) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS teamwork_raw (
            holder_name TEXT,
            holder_type TEXT,
            coholder_name TEXT,
            coholder_type TEXT,
            co_count INTEGER,
            company_detail TEXT,
            PRIMARY KEY (holder_name, coholder_name)
        )
        """
    )
    conn.execute("DELETE FROM teamwork_raw")
    rows = []
    for _, r in df.iterrows():
        rows.append(
            (
                r.get("股东名称"),
                r.get("股东类型"),
                r.get("协同股东名称"),
                r.get("协同股东类型"),
                int(r.get("协同次数") or 0),
                r.get("个股详情") or "",
            )
        )
    conn.executemany(
        "INSERT OR REPLACE INTO teamwork_raw VALUES (?, ?, ?, ?, ?, ?)", rows
    )
