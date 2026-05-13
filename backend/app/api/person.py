from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models import DisambiguateResponse, PersonDetail

router = APIRouter(tags=["person"])


@router.get("/person/{name}", response_model=PersonDetail)
def person_detail(name: str, bucket: int | None = None) -> PersonDetail:
    # TODO(PR 5): port bucket-aware aggregation from assets/v2-prototype.py:158.
    raise HTTPException(status_code=501, detail="person_detail not yet ported")


@router.get("/person/{name}/disambiguate", response_model=DisambiguateResponse)
def disambiguate(name: str) -> DisambiguateResponse:
    # TODO(PR 8): port _compute_buckets / disambiguate algorithm.
    raise HTTPException(status_code=501, detail="disambiguate not yet ported")
