from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.db.connection import connect
from app.models import (
    BucketMeta,
    BucketSummary,
    CoholderSummary,
    CompanyHolding,
    DisambiguateResponse,
    PersonDetail,
    SingletonPreview,
    TotalValuePoint,
    WikidataProfile,
)
from app.services.disambiguate import Bucket, compute_buckets
from app.services.heuristics import is_person_heuristic
from app.services.wikidata import wikidata_lookup

router = APIRouter(tags=["person"])


@router.get("/person/{name}", response_model=PersonDetail)
def person_detail(name: str, bucket: int | None = None) -> PersonDetail:
    bucket_codes: set[str] | None = None
    bucket_meta: BucketMeta | None = None
    if bucket is not None:
        buckets = _safe_buckets(name)
        if buckets is None:
            raise HTTPException(status_code=404, detail="name not found")
        target = next((b for b in buckets if b.bucket_idx == bucket), None)
        if target is None:
            raise HTTPException(status_code=404, detail=f"bucket {bucket} not found")
        bucket_codes = {c[0] for c in target.companies}
        bucket_meta = BucketMeta(
            bucket_idx=bucket,
            size=target.size,
            level=target.level,
            label=target.label,
            evidence=target.evidence,
            total_buckets=len(buckets),
        )

    companies, total_series, source = _load_companies(name, bucket_codes)
    if not companies and source == "missing":
        raise HTTPException(status_code=404, detail="person not found")
    peers = _load_coholders(name, bucket_codes, bucket_target=_target_if_bucket(name, bucket))
    profile = _safe_wikidata(name)
    return PersonDetail(
        name=name,
        wikidata=profile,
        companies=companies,
        total_value_series=total_series,
        coholders=peers,
        data_source=source if source != "missing" else "raw_name",
        bucket_meta=bucket_meta,
    )


@router.get("/person/{name}/disambiguate", response_model=DisambiguateResponse)
def disambiguate(name: str) -> DisambiguateResponse:
    buckets = _safe_buckets(name)
    if buckets is None:
        raise HTTPException(status_code=404, detail="name not found")
    multi = [b for b in buckets if b.bucket_idx is not None]
    singles = [b for b in buckets if b.bucket_idx is None]
    return DisambiguateResponse(
        name=name,
        total_companies=sum(b.size for b in buckets),
        total_buckets=len(buckets),
        multi_company_buckets=len(multi),
        singletons=len(singles),
        buckets=[
            BucketSummary(
                bucket_idx=b.bucket_idx if b.bucket_idx is not None else 0,
                size=b.size,
                level=b.level,
                label=b.label,
                evidence=b.evidence,
                top_peers=[p[0] for p in b.top_peers],
                companies=[c[0] for c in b.companies],
            )
            for b in multi
        ],
        singletons_preview=[
            SingletonPreview(
                bucket_idx=0,
                stock_code=b.companies[0][0],
                stock_name=b.companies[0][1],
            )
            for b in singles[:30]
            if b.companies
        ],
    )


def _safe_buckets(name: str) -> list[Bucket] | None:
    try:
        with connect("entities") as conn:
            buckets, _, _ = compute_buckets(conn, name)
            return buckets
    except Exception:
        return None


def _target_if_bucket(name: str, bucket: int | None) -> Bucket | None:
    if bucket is None:
        return None
    buckets = _safe_buckets(name)
    if buckets is None:
        return None
    return next((b for b in buckets if b.bucket_idx == bucket), None)


def _load_companies(
    name: str, bucket_codes: set[str] | None
) -> tuple[list[CompanyHolding], list[TotalValuePoint], str]:
    """Load detailed timeline rows from holdings + prices; fall back to teamwork snapshot."""
    rows: list = []
    try:
        with connect("holdings") as conn:
            rows = conn.execute(
                """
                SELECT t.report_date, t.stock_code, t.stock_name,
                       t.holdings, t.pct_total, t.rank,
                       fh.holder_nature, fh.pct_free
                FROM top10_holders t
                LEFT JOIN top10_free_holders fh
                       ON t.stock_code = fh.stock_code
                      AND t.report_date = fh.report_date
                      AND t.holder_name = fh.holder_name
                WHERE t.holder_name = ?
                ORDER BY t.report_date, t.stock_code
                """,
                (name,),
            ).fetchall()
    except Exception:
        rows = []
    if bucket_codes is not None:
        rows = [r for r in rows if r["stock_code"] in bucket_codes]

    if not rows:
        snap = _load_teamwork_snapshot(name, bucket_codes)
        if not snap:
            return [], [], "missing"
        return snap, [], "raw_name"

    by_company: dict[str, dict] = {}
    total_by_date: dict[str, float] = {}
    for r in rows:
        # Defensive: legacy ETL (before pull_top10._upsert alignment fix) could
        # write NULL stock_code/report_date for some holders. Skip these.
        if r["stock_code"] is None or r["report_date"] is None:
            continue
        close = _close_on_or_before(r["stock_code"], r["report_date"])
        mv = (r["holdings"] * close) if (close and r["holdings"]) else None
        entry = by_company.setdefault(
            r["stock_code"],
            {
                "stock_code": r["stock_code"],
                "stock_name": r["stock_name"],
                "report_date": r["report_date"],
                "rank": r["rank"],
                "holdings": r["holdings"],
                "pct_total": r["pct_total"],
                "pct_free": r["pct_free"],
                "holdings_value": mv,
                "source_table": "top10_holders",
            },
        )
        # Keep latest report_date per company.
        if r["report_date"] >= entry["report_date"]:
            entry.update(
                {
                    "report_date": r["report_date"],
                    "rank": r["rank"],
                    "holdings": r["holdings"],
                    "pct_total": r["pct_total"],
                    "pct_free": r["pct_free"],
                    "holdings_value": mv,
                }
            )
        if mv is not None:
            total_by_date[r["report_date"]] = total_by_date.get(r["report_date"], 0) + mv

    companies = [CompanyHolding(**v) for v in by_company.values()]
    total_series = [
        TotalValuePoint(date=d, value=v) for d, v in sorted(total_by_date.items())
    ]
    return companies, total_series, "entity"


def _load_teamwork_snapshot(
    name: str, bucket_codes: set[str] | None
) -> list[CompanyHolding]:
    try:
        with connect("entities") as conn:
            rows = conn.execute(
                """
                SELECT stock_code, stock_name, report_date
                FROM holder_companies
                WHERE holder_name = ?
                """,
                (name,),
            ).fetchall()
    except Exception:
        return []
    if bucket_codes is not None:
        rows = [r for r in rows if r["stock_code"] in bucket_codes]
    return [
        CompanyHolding(
            stock_code=r["stock_code"],
            stock_name=r["stock_name"],
            report_date=r["report_date"],
            rank=0,
            holdings=0,
            pct_total=None,
            pct_free=None,
            holdings_value=None,
            source_table="holder_companies",
        )
        for r in rows
    ]


def _load_coholders(
    name: str, bucket_codes: set[str] | None, bucket_target: Bucket | None
) -> list[CoholderSummary]:
    if bucket_target is not None:
        return [
            CoholderSummary(name=p[0], co_count=p[1], is_person=True)
            for p in bucket_target.top_peers
        ]
    try:
        with connect("entities") as conn:
            rows = conn.execute(
                """
                SELECT holder_a, holder_a_type, holder_b, holder_b_type, co_count
                FROM coholder_pairs
                WHERE (holder_a = ? OR holder_b = ?) AND co_count >= 2
                  AND holder_a_type = '个人' AND holder_b_type = '个人'
                ORDER BY co_count DESC LIMIT 30
                """,
                (name, name),
            ).fetchall()
    except Exception:
        return []
    seen: set[str] = set()
    out: list[CoholderSummary] = []
    for r in rows:
        peer = r["holder_b"] if r["holder_a"] == name else r["holder_a"]
        if peer in seen:
            continue
        seen.add(peer)
        out.append(
            CoholderSummary(
                name=peer,
                co_count=r["co_count"],
                is_person=is_person_heuristic(peer, "个人"),
            )
        )
    return out


def _close_on_or_before(code: str, date: str) -> float | None:
    try:
        with connect("prices") as conn:
            r = conn.execute(
                """
                SELECT close FROM stock_daily_price
                 WHERE stock_code = ? AND adjust = '' AND date <= ?
                 ORDER BY date DESC LIMIT 1
                """,
                (code, date),
            ).fetchone()
            return r["close"] if r else None
    except Exception:
        return None


def _safe_wikidata(name: str) -> WikidataProfile | None:
    try:
        return wikidata_lookup(name)
    except Exception:
        return None
