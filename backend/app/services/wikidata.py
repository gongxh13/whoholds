"""Cache-first Wikidata lookup.

Reads `wd_cache.db` for an existing entry; returns `None` if the cache misses.
PR 7+ ETL is responsible for populating the cache; per design.md we never call
Wikidata from the request path (latency + rate-limit risk on a shared key).
"""
from __future__ import annotations

import sqlite3

from app.config import DB_PATHS
from app.models import WikidataProfile


def wikidata_lookup(name: str) -> WikidataProfile | None:
    path = DB_PATHS["wd_cache"]
    if not path.exists():
        return None
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT * FROM wd_cache WHERE name = ?", (name,)).fetchone()
    except sqlite3.OperationalError:
        return None
    finally:
        conn.close()
    if not row:
        return None
    return WikidataProfile(
        name=name,
        qid=row["qid"],
        label=row["label"],
        description=row["description"],
        birth=row["birth"],
        occupations=row["occupations"],
        employer=row["employer"],
        zh_wiki=row["zh_wiki"],
    )
