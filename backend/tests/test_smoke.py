from __future__ import annotations

from fastapi.testclient import TestClient


def _client() -> TestClient:
    from app.main import app

    return TestClient(app)


def test_health_ok() -> None:
    r = _client().get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert set(body["databases"]) == {"holdings", "prices", "entities", "wd_cache", "meta"}
    assert all(body["databases"].values())  # conftest migrates all 5


def test_openapi_has_all_routes() -> None:
    r = _client().get("/openapi.json")
    assert r.status_code == 200
    paths = set(r.json()["paths"])
    expected = {
        "/api/health",
        "/api/search",
        "/api/person/{name}",
        "/api/person/{name}/disambiguate",
        "/api/company/{code}",
        "/api/network",
        "/api/discover/top-cross-holders",
        "/api/discover/top-coholder-pairs",
        "/api/annotation",
    }
    missing = expected - paths
    assert not missing, f"missing routes: {missing}"


def test_search_empty_db_returns_empty_lists() -> None:
    r = _client().get("/api/search", params={"q": "x"})
    assert r.status_code == 200
    body = r.json()
    assert body == {"people": [], "companies": []}


def test_company_404_when_unknown() -> None:
    r = _client().get("/api/company/sh999999")
    assert r.status_code == 404


def test_discover_pairs_empty() -> None:
    r = _client().get("/api/discover/top-coholder-pairs")
    assert r.status_code == 200
    assert r.json() == []
