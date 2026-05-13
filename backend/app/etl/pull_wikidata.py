"""Fill `wd_cache.db` for a list of names — Wikidata wbsearchentities + SPARQL.

design.md §Wikidata 实证: head-coverage decent (王传福/方洪波 hit), tail very
sparse, name collisions common (黄健 etc.). We cache *negative* hits with
qid=NULL so we don't re-query.
"""
from __future__ import annotations

import time
from collections.abc import Iterable

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.etl.common import JobStatus, alert, record_progress, write_db

JOB = "pull_wikidata"
WD_SEARCH = "https://www.wikidata.org/w/api.php"
WD_SPARQL = "https://query.wikidata.org/sparql"
UA = "whoholds/0.1 (https://github.com/whoholds)"


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
def _search(name: str, client: httpx.Client) -> dict | None:
    r = client.get(
        WD_SEARCH,
        params={
            "action": "wbsearchentities",
            "search": name,
            "language": "zh",
            "format": "json",
            "limit": 1,
        },
        headers={"User-Agent": UA},
        timeout=10,
    )
    r.raise_for_status()
    results = r.json().get("search", [])
    return results[0] if results else None


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
def _sparql(qid: str, client: httpx.Client) -> dict:
    query = f"""
    SELECT ?occLabel ?bd ?empLabel ?wiki WHERE {{
      OPTIONAL {{ wd:{qid} wdt:P106 ?occ. }}
      OPTIONAL {{ wd:{qid} wdt:P569 ?bd. }}
      OPTIONAL {{ wd:{qid} wdt:P108 ?emp. }}
      OPTIONAL {{ ?wiki schema:about wd:{qid}; schema:isPartOf <https://zh.wikipedia.org/>. }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "zh,en". }}
    }} LIMIT 20
    """
    r = client.get(
        WD_SPARQL,
        params={"query": query, "format": "json"},
        headers={"User-Agent": UA},
        timeout=15,
    )
    r.raise_for_status()
    binds = r.json().get("results", {}).get("bindings", [])
    return {
        "occupations": "/".join(sorted({b["occLabel"]["value"] for b in binds if "occLabel" in b})),
        "births": sorted({b["bd"]["value"][:10] for b in binds if "bd" in b}),
        "employers": "/".join(sorted({b["empLabel"]["value"] for b in binds if "empLabel" in b})),
        "wikis": sorted({b["wiki"]["value"] for b in binds if "wiki" in b}),
    }


def pull_one(name: str, client: httpx.Client | None = None) -> JobStatus:
    own_client = client is None
    client = client or httpx.Client()
    try:
        try:
            hit = _search(name, client)
        except Exception as exc:  # noqa: BLE001
            alert("warn", JOB, f"search {name}: {exc}")
            return JobStatus(JOB, name, "error", str(exc))
        conn = write_db("wd_cache")
        try:
            if hit is None:
                conn.execute(
                    "INSERT OR REPLACE INTO wd_cache (name, fetched_at) VALUES (?, ?)",
                    (name, int(time.time())),
                )
                conn.commit()
                return JobStatus(JOB, name, "ok")
            qid = hit["id"]
            details = _sparql(qid, client)
            conn.execute(
                """
                INSERT OR REPLACE INTO wd_cache
                    (name, qid, label, description, birth, occupations, employer, zh_wiki, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    name,
                    qid,
                    hit.get("label"),
                    hit.get("description", ""),
                    details["births"][0] if details["births"] else "",
                    details["occupations"],
                    details["employers"],
                    details["wikis"][0] if details["wikis"] else "",
                    int(time.time()),
                ),
            )
            conn.commit()
        finally:
            conn.close()
    finally:
        if own_client:
            client.close()
    status = JobStatus(JOB, name, "ok")
    record_progress(status)
    return status


def pull_batch(names: Iterable[str]) -> int:
    n = 0
    with httpx.Client() as client:
        for name in names:
            if pull_one(name, client).status == "ok":
                n += 1
            time.sleep(0.2)  # be polite to Wikidata
    return n
