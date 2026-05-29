"""Healthcheck endpoint tests (AC: GET /healthz returns 200 {"status":"ok"})."""

from fastapi.testclient import TestClient


def test_healthz_returns_ok(client: TestClient) -> None:
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_healthz_content_type_json(client: TestClient) -> None:
    response = client.get("/healthz")

    assert response.headers["content-type"].startswith("application/json")
