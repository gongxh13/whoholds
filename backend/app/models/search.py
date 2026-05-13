from __future__ import annotations

from pydantic import BaseModel


class SearchPerson(BaseModel):
    name: str
    n_companies: int | None = None


class SearchCompany(BaseModel):
    stock_code: str
    stock_name: str


class SearchResponse(BaseModel):
    people: list[SearchPerson]
    companies: list[SearchCompany]
