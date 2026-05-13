from __future__ import annotations

from pydantic import BaseModel


class Top10Row(BaseModel):
    rank: int
    holder_name: str
    share_type: str | None = None
    holdings: int
    pct: float | None = None
    pct_field: str
    change_value: str | None = None
    change_pct: float | None = None
    is_person: bool
    source_table: str
    holdings_value: float | None = None


class StackSeriesPoint(BaseModel):
    date: str
    holder_name: str
    holdings: int
    holdings_value: float | None = None


class CompanyDetail(BaseModel):
    stock_code: str
    stock_name: str
    available_dates: list[str]
    current_date: str | None
    top10: list[Top10Row]
    stack_series: list[StackSeriesPoint]
