"""ETL job: rebuild `entity` + `appearance_entity` for every raw_name.

For each unique `holder_name` in `holder_companies`, run the Layer 2 algorithm
in `services.disambiguate` and persist its buckets as `entity` rows. Each
appearance (stock_code, holder_name) gets a pointer into its bucket.

Idempotent: full recompute clears both tables and rewrites them. Per design.md
the daily 04:00 job runs this; PR 10 will add an incremental variant that only
recomputes for names whose appearances changed.
"""
from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from app.etl.common import JobStatus, record_progress, write_db
from app.services.disambiguate import compute_buckets
from app.services.heuristics import is_person_heuristic

JOB = "disambiguate"


def run(*, names: list[str] | None = None) -> JobStatus:
    """Rebuild entities. If `names` given, only those — else whole market."""
    conn = write_db("entities")
    try:
        conn.row_factory = sqlite3.Row
        if names is None:
            names = _all_names(conn)
            conn.execute("DELETE FROM entity")
            conn.execute("DELETE FROM appearance_entity")
        next_id = _max_entity_id(conn) + 1
        n_buckets = 0
        for name in names:
            buckets, _, _ = compute_buckets(conn, name)
            if not buckets:
                continue
            for b in buckets:
                canonical = name if len(buckets) == 1 else f"{name}#{b.bucket_idx or 'single'}"
                conn.execute(
                    """
                    INSERT INTO entity
                        (entity_id, canonical_name, raw_name, confidence_level,
                         evidence, wikidata_qid, manual_override, updated_at)
                    VALUES (?, ?, ?, ?, ?, NULL, 0, ?)
                    """,
                    (
                        next_id,
                        canonical,
                        name,
                        b.level,
                        b.evidence,
                        _now(),
                    ),
                )
                for code, _ in b.companies:
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO appearance_entity
                            (stock_code, holder_name, entity_id)
                        VALUES (?, ?, ?)
                        """,
                        (code, name, next_id),
                    )
                next_id += 1
                n_buckets += 1
        conn.commit()
    finally:
        conn.close()
    print(f"[disambiguate] {n_buckets} buckets written for {len(names)} names", flush=True)
    status = JobStatus(JOB, f"names={len(names)}", "ok")
    record_progress(status)
    return status


def is_person_three_layer(
    conn: sqlite3.Connection, name: str, nature: str | None
) -> bool:
    """Three-layer is_person decision used by ETL when populating top10 rows."""
    override = conn.execute(
        """
        SELECT payload FROM user_annotation
        WHERE op = 'is_person' AND payload LIKE ?
        ORDER BY id DESC LIMIT 1
        """,
        (f'%"name": "{name}"%',),
    ).fetchone()
    if override:
        return '"value": true' in override["payload"]
    return is_person_heuristic(name, nature)


def _all_names(conn: sqlite3.Connection) -> list[str]:
    return [
        r["holder_name"]
        for r in conn.execute(
            "SELECT DISTINCT holder_name FROM holder_companies WHERE holder_type = '个人'"
        )
    ]


def _max_entity_id(conn: sqlite3.Connection) -> int:
    r = conn.execute("SELECT MAX(entity_id) FROM entity").fetchone()
    return (r[0] or 0)


def _now() -> str:
    return datetime.now(UTC).isoformat()
