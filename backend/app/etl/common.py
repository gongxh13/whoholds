"""Shared ETL utilities — limiter, retry decorator, dead_letter / alert writers."""
from __future__ import annotations

import asyncio
import sqlite3
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TypeVar

from app.config import DB_PATHS

T = TypeVar("T")

# Per-host async semaphore; 8 concurrent in-flight per host is the design.md
# limit (avoids tripping eastmoney/tencent rate caps).
_LIMITERS: dict[str, asyncio.Semaphore] = {}


def host_limiter(host: str, *, capacity: int = 8) -> asyncio.Semaphore:
    sem = _LIMITERS.get(host)
    if sem is None:
        sem = asyncio.Semaphore(capacity)
        _LIMITERS[host] = sem
    return sem


@dataclass(slots=True)
class JobStatus:
    job: str
    key: str
    status: str  # 'ok' / 'error' / 'skipped'
    error: str | None = None


def record_progress(status: JobStatus) -> None:
    """Persist a job/key outcome into meta.etl_progress."""
    path = DB_PATHS["meta"]
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            """
            INSERT INTO etl_progress (job_name, key, status, attempted_at, last_error)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(job_name, key) DO UPDATE SET
                status = excluded.status,
                attempted_at = excluded.attempted_at,
                last_error = excluded.last_error
            """,
            (status.job, status.key, status.status, _now(), status.error),
        )
        conn.commit()
    finally:
        conn.close()


def dead_letter(job: str, key: str, payload: str, error: str) -> None:
    path = DB_PATHS["meta"]
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            "INSERT INTO dead_letter (job, key, payload, error, ts) VALUES (?, ?, ?, ?, ?)",
            (job, key, payload, error, _now()),
        )
        conn.commit()
    finally:
        conn.close()


def alert(severity: str, component: str, message: str) -> None:
    path = DB_PATHS["meta"]
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            "INSERT INTO alert (severity, component, message, ts) VALUES (?, ?, ?, ?)",
            (severity, component, message, _now()),
        )
        conn.commit()
    finally:
        conn.close()


def already_succeeded(job: str, key: str) -> bool:
    """Idempotency check — used by incremental jobs to skip done keys."""
    path = DB_PATHS["meta"]
    if not path.exists():
        return False
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        row = conn.execute(
            "SELECT status FROM etl_progress WHERE job_name = ? AND key = ?",
            (job, key),
        ).fetchone()
        return bool(row and row[0] == "ok")
    finally:
        conn.close()


def write_db(name: str) -> sqlite3.Connection:
    """Open a write connection with WAL mode (sqlite single-writer + many-reader)."""
    path = DB_PATHS[name]
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


def _now() -> str:
    return datetime.now(UTC).isoformat()


async def gather_with_progress(
    coros: list, *, label: str, every: int = 50
) -> list:
    """Run a batch of coroutines, logging progress every `every` completions."""
    results = []
    t0 = time.time()
    for i, coro in enumerate(asyncio.as_completed(coros), 1):
        results.append(await coro)
        if i % every == 0:
            print(f"[{label}] {i}/{len(coros)} done in {time.time()-t0:.0f}s", flush=True)
    return results


def safe_run(fn: Callable[..., T], *args, fallback: T | None = None) -> T | None:
    try:
        return fn(*args)
    except Exception as exc:  # noqa: BLE001
        alert("warn", fn.__module__, f"{fn.__name__}: {exc}")
        return fallback
