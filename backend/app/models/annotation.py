from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

AnnotationOp = Literal["merge", "split", "bind_qid", "is_person"]


class AnnotationRequest(BaseModel):
    op: AnnotationOp
    payload: dict[str, Any]
    user: str = "anonymous"


class AnnotationResponse(BaseModel):
    id: int
    op: AnnotationOp
    payload: dict[str, Any]
    user: str
    ts: str
