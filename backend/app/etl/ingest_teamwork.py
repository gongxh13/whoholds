"""Expand `teamwork_raw` into `holder_companies` + `coholder_pairs`.

The raw `个股详情` field is a comma-separated list of `code|name|YYYY-MM-DD`
segments. We split it into per-(holder × company) rows for fast lookup and
keep the pair-level record (with co_count) for the discover view.
"""
from __future__ import annotations

import sqlite3

from app.etl.common import JobStatus, record_progress, write_db
from app.services.heuristics import market_prefix

JOB = "ingest_teamwork"


def run() -> JobStatus:
    conn = write_db("entities")
    try:
        conn.execute("DELETE FROM holder_companies")
        conn.execute("DELETE FROM coholder_pairs")
        n_hc, n_cp = _expand(conn)
        conn.commit()
    finally:
        conn.close()
    print(
        f"[ingest_teamwork] holder_companies={n_hc}, coholder_pairs={n_cp}",
        flush=True,
    )
    status = JobStatus(JOB, "full", "ok")
    record_progress(status)
    return status


def _expand(conn: sqlite3.Connection) -> tuple[int, int]:
    rows = conn.execute(
        """
        SELECT holder_name, holder_type, coholder_name, coholder_type, co_count, company_detail
        FROM teamwork_raw
        """
    ).fetchall()
    hc: list[tuple] = []
    cp: list[tuple] = []
    for r in rows:
        holder_name, holder_type, coholder_name, coholder_type, co_count, detail = r
        companies: list[tuple[str, str, str]] = []
        for seg in (detail or "").split(","):
            parts = seg.split("|")
            if len(parts) < 3:
                continue
            code = market_prefix(parts[0])
            name = parts[1].strip()
            date = parts[2].strip().replace("-", "")[:8]
            companies.append((code, name, date))
        for code, name, date in companies:
            hc.append((holder_name, holder_type, code, name, date))
        cp.append(
            (
                holder_name,
                holder_type,
                coholder_name,
                coholder_type,
                int(co_count or 0),
                ",".join(f"{c[0]}|{c[1]}|{c[2]}" for c in companies),
            )
        )
    if hc:
        conn.executemany(
            "INSERT OR IGNORE INTO holder_companies VALUES (?, ?, ?, ?, ?)", hc
        )
    if cp:
        conn.executemany(
            "INSERT OR IGNORE INTO coholder_pairs VALUES (?, ?, ?, ?, ?, ?)", cp
        )
    return len(hc), len(cp)
