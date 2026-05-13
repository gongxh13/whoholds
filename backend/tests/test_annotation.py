from __future__ import annotations

from fastapi.testclient import TestClient


def _client() -> TestClient:
    from app.main import app

    return TestClient(app)


def test_annotation_create_and_list() -> None:
    body = {
        "op": "bind_qid",
        "payload": {"name": "王传福", "qid": "Q716030"},
        "user": "tester",
    }
    r = _client().post("/api/annotation", json=body)
    assert r.status_code == 200
    created = r.json()
    assert created["op"] == "bind_qid"
    assert created["payload"] == body["payload"]
    assert created["user"] == "tester"
    assert isinstance(created["id"], int)

    r2 = _client().get("/api/annotation")
    assert r2.status_code == 200
    listed = r2.json()
    assert any(a["id"] == created["id"] for a in listed)


def test_annotation_empty_payload_rejected() -> None:
    r = _client().post(
        "/api/annotation",
        json={"op": "merge", "payload": {}, "user": "x"},
    )
    assert r.status_code == 422
