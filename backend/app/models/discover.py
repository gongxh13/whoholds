from __future__ import annotations

from pydantic import BaseModel


class CrossHolderCompany(BaseModel):
    stock_code: str
    stock_name: str
    pct_total: float | None = None
    holdings: int


class CrossHolder(BaseModel):
    holder_name: str
    n_companies: int
    companies: list[CrossHolderCompany]
    total_value: float | None = None


class CoholderPair(BaseModel):
    holder_a: str
    holder_b: str
    co_count: int
    company_list: str
