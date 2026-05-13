from __future__ import annotations

from pydantic import BaseModel

from app.models.common import ConfidenceLevel, DataSource


class WikidataProfile(BaseModel):
    name: str
    qid: str | None = None
    label: str | None = None
    description: str | None = None
    birth: str | None = None
    occupations: str | None = None
    employer: str | None = None
    zh_wiki: str | None = None


class CompanyHolding(BaseModel):
    stock_code: str
    stock_name: str
    report_date: str
    rank: int
    holdings: int
    pct_total: float | None = None
    pct_free: float | None = None
    holdings_value: float | None = None
    source_table: str


class TotalValuePoint(BaseModel):
    date: str
    value: float


class CoholderSummary(BaseModel):
    name: str
    co_count: int
    is_person: bool


class BucketMeta(BaseModel):
    bucket_idx: int
    size: int
    level: ConfidenceLevel
    label: str
    evidence: str
    total_buckets: int


class PersonDetail(BaseModel):
    name: str
    data_source: DataSource
    bucket_meta: BucketMeta | None = None
    wikidata: WikidataProfile | None = None
    companies: list[CompanyHolding]
    total_value_series: list[TotalValuePoint]
    coholders: list[CoholderSummary]


class BucketSummary(BaseModel):
    bucket_idx: int
    size: int
    level: ConfidenceLevel
    label: str
    evidence: str
    top_peers: list[str]
    companies: list[str]


class SingletonPreview(BaseModel):
    bucket_idx: int
    stock_code: str
    stock_name: str


class DisambiguateResponse(BaseModel):
    name: str
    total_companies: int
    total_buckets: int
    multi_company_buckets: int
    singletons: int
    buckets: list[BucketSummary]
    singletons_preview: list[SingletonPreview]
