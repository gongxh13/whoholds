"""Layer 2 same-name disambiguation (the validated core algorithm).

For a given raw name N:
  1. Collect every (company, date) appearance of N from `holder_companies`.
  2. For each company c, build S(c) = set of *individual* coholders of N in c.
  3. Build a graph over companies; connect c1↔c2 when |S(c1) ∩ S(c2)| ≥ 1.
  4. Union-find connected components — each component is one candidate bucket.

See design.md §同名消歧算法 for evidence / confidence labels.
"""
from __future__ import annotations

import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Literal

from app.services.heuristics import is_person_heuristic, market_prefix

ConfidenceLevel = Literal["high", "mid", "low", "single"]


@dataclass(slots=True)
class Bucket:
    bucket_idx: int | None  # None for singletons
    size: int
    level: ConfidenceLevel
    label: str
    evidence: str
    top_peers: list[tuple[str, int]]  # (peer_name, freq)
    companies: list[tuple[str, str]]  # (code, name)


def _peer_companies(
    conn: sqlite3.Connection, name: str, own_companies: set[str]
) -> dict[str, set[str]]:
    """For each of name's own companies, collect the set of non-trivial individual coholders."""
    by_co: dict[str, set[str]] = {c: set() for c in own_companies}
    rows = conn.execute(
        """
        SELECT holder_b, company_list FROM coholder_pairs
         WHERE holder_a = ? AND holder_b_type = '个人' AND holder_b != ?
        """,
        (name, name),
    ).fetchall()
    for row in rows:
        peer = row["holder_b"] if isinstance(row, sqlite3.Row) else row[0]
        company_list = row["company_list"] if isinstance(row, sqlite3.Row) else row[1]
        if not is_person_heuristic(peer, "个人"):
            continue
        for seg in (company_list or "").split(","):
            parts = seg.split("|")
            if not parts or not parts[0].strip():
                continue
            # company_list is produced by ingest_teamwork already with market prefix
            # (sh/sz/bj). market_prefix() is idempotent so this is safe either way,
            # but explicit is better than implicit.
            full = parts[0].strip()
            if full in by_co:
                by_co[full].add(peer)
    return by_co


def _label_for(size: int, top_peer_freq: int) -> tuple[ConfidenceLevel, str]:
    is_multi = size >= 2
    if size >= 5 and top_peer_freq >= 3:
        return "high", "高置信"
    if is_multi and top_peer_freq >= 2:
        return "mid", "中置信"
    if is_multi:
        return "low", "低置信"
    return "single", "单飞"


def compute_buckets(
    conn: sqlite3.Connection, name: str
) -> tuple[list[Bucket], dict[str, int | None], dict[str, str]] | tuple[None, None, None]:
    """Run the disambiguation algorithm. Returns (buckets, code→idx, code→name)."""
    conn.row_factory = sqlite3.Row
    company_rows = conn.execute(
        "SELECT DISTINCT stock_code FROM holder_companies WHERE holder_name = ?",
        (name,),
    ).fetchall()
    companies = [r["stock_code"] for r in company_rows]
    if not companies:
        return None, None, None

    placeholders = ",".join("?" * len(companies))
    code_to_name = {
        r["stock_code"]: r["stock_name"]
        for r in conn.execute(
            f"SELECT stock_code, stock_name FROM holder_companies WHERE stock_code IN ({placeholders})",
            companies,
        )
    }

    by_co = _peer_companies(conn, name, set(companies))

    # Union-find over companies that share ≥ 1 individual peer.
    parent: dict[str, str] = {c: c for c in companies}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for i, a in enumerate(companies):
        for b in companies[i + 1 :]:
            if by_co[a] & by_co[b]:
                union(a, b)

    groups: dict[str, list[str]] = defaultdict(list)
    for c in companies:
        groups[find(c)].append(c)

    raw: list[dict] = []
    for root, codes in groups.items():
        peers: Counter[str] = Counter()
        for c in codes:
            for p in by_co[c]:
                peers[p] += 1
        raw.append({"root": root, "codes": codes, "peers": peers})

    raw.sort(
        key=lambda b: (-len(b["codes"]), -max(b["peers"].values()) if b["peers"] else 0)
    )

    buckets: list[Bucket] = []
    code_to_bucket: dict[str, int | None] = {}
    multi_idx = 0
    for b in raw:
        size = len(b["codes"])
        peers_counter: Counter[str] = b["peers"]
        top_peer_freq = max(peers_counter.values()) if peers_counter else 0
        is_multi = size >= 2
        idx: int | None
        if is_multi:
            multi_idx += 1
            idx = multi_idx
        else:
            idx = None
        level, label = _label_for(size, top_peer_freq)
        top_peer = peers_counter.most_common(1)
        evidence = (
            f"与{top_peer[0][0]}同公司 {top_peer[0][1]} 次"
            if top_peer
            else "无个人协同信号"
        )
        bucket = Bucket(
            bucket_idx=idx,
            size=size,
            level=level,
            label=label,
            evidence=evidence,
            top_peers=peers_counter.most_common(5),
            companies=[(c, code_to_name.get(c, c)) for c in sorted(b["codes"])],
        )
        buckets.append(bucket)
        for c in b["codes"]:
            code_to_bucket[c] = idx
    return buckets, code_to_bucket, code_to_name
