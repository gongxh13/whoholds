"""User-annotation surface (PR 10).

Three operations, all written to entities.user_annotation as an audit trail:
- merge:      payload = {"names": ["吕强", "李红"], "into": canonical_name}
- split:      payload = {"name": "张秀", "bucket": 3, "into": [["sh600xxx", ...]]}
- bind_qid:   payload = {"name": "王传福", "bucket": null, "qid": "Q716030"}
- is_person:  payload = {"name": "某人", "value": true|false}

After writing, we schedule a re-disambiguation of the touched names.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException

from app.config import DB_PATHS
from app.models import AnnotationRequest, AnnotationResponse

router = APIRouter(tags=["annotation"])


@router.post("/annotation", response_model=AnnotationResponse)
def create_annotation(req: AnnotationRequest) -> AnnotationResponse:
    if not req.payload:
        raise HTTPException(status_code=422, detail="payload required")
    path = DB_PATHS["entities"]
    path.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).isoformat()
    conn = sqlite3.connect(path)
    try:
        cur = conn.execute(
            "INSERT INTO user_annotation (op, payload, user, ts) VALUES (?, ?, ?, ?)",
            (req.op, json.dumps(req.payload, ensure_ascii=False), req.user, ts),
        )
        conn.commit()
        new_id = cur.lastrowid or 0
    finally:
        conn.close()

    # Best-effort: rebuild entities for touched raw names. Skipped if heavy.
    _trigger_recompute(req)

    return AnnotationResponse(
        id=new_id, op=req.op, payload=req.payload, user=req.user, ts=ts
    )


@router.get("/annotation", response_model=list[AnnotationResponse])
def list_annotations(limit: int = 50) -> list[AnnotationResponse]:
    path = DB_PATHS["entities"]
    if not path.exists():
        return []
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT id, op, payload, user, ts FROM user_annotation ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    finally:
        conn.close()
    return [
        AnnotationResponse(
            id=r["id"],
            op=r["op"],
            payload=json.loads(r["payload"] or "{}"),
            user=r["user"],
            ts=r["ts"],
        )
        for r in rows
    ]


def _trigger_recompute(req: AnnotationRequest) -> None:
    """Re-run disambiguation for the touched names — best-effort, swallow errors."""
    names: list[str] = []
    if req.op in ("split", "bind_qid", "is_person"):
        n = req.payload.get("name")
        if isinstance(n, str):
            names.append(n)
    elif req.op == "merge":
        ns = req.payload.get("names")
        if isinstance(ns, list):
            names.extend(x for x in ns if isinstance(x, str))
    if not names:
        return
    try:
        from app.etl.disambiguate import run as recompute

        recompute(names=names)
    except Exception:  # noqa: BLE001
        return
