from __future__ import annotations

from pydantic import BaseModel


class NetworkNode(BaseModel):
    id: str
    label: str
    kind: str
    is_person: bool | None = None
    hop: int


class NetworkEdge(BaseModel):
    source: str
    target: str
    weight: float
    kind: str


class NetworkStats(BaseModel):
    n_nodes: int
    n_edges: int
    truncated: bool


class NetworkResponse(BaseModel):
    focus: str
    nodes: list[NetworkNode]
    edges: list[NetworkEdge]
    stats: NetworkStats
