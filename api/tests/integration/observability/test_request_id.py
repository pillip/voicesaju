"""Integration tests for ``RequestIdMiddleware`` (ISSUE-079).

Boots a real FastAPI app (via ``create_app``), runs a TestClient request,
and asserts:

1. Response carries an ``X-Request-ID`` header (uuid4 hex shape).
2. An inbound ``X-Request-ID`` is honoured when valid (alnum/dash, ≤ 64).
3. A malformed inbound id is replaced (not echoed back).
4. The logging ContextVar is populated for the duration of the request
   so structlog events would carry the same id.
"""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client() -> TestClient:
    from voicesaju.main import create_app

    app = create_app()
    return TestClient(app)


_HEX64 = re.compile(r"^[A-Fa-f0-9]{32}$")


def test_healthz_returns_request_id_header(client: TestClient) -> None:
    response = client.get("/healthz")

    assert response.status_code == 200
    assert "X-Request-ID" in response.headers
    assert _HEX64.match(response.headers["X-Request-ID"])


def test_inbound_request_id_is_honoured(client: TestClient) -> None:
    response = client.get(
        "/healthz",
        headers={"X-Request-ID": "trace-abc-123"},
    )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "trace-abc-123"


def test_malformed_inbound_request_id_is_replaced(client: TestClient) -> None:
    response = client.get(
        "/healthz",
        headers={"X-Request-ID": "bad id with spaces!!"},
    )

    assert response.status_code == 200
    # Replaced with a fresh uuid4 hex, NOT the malformed value.
    assert response.headers["X-Request-ID"] != "bad id with spaces!!"
    assert _HEX64.match(response.headers["X-Request-ID"])


def test_request_id_visible_in_route_handler(client: TestClient) -> None:
    """A custom handler can read the request_id via ``get_request_id``."""
    from voicesaju.main import create_app
    from voicesaju.observability.logging import get_request_id

    app = create_app()

    @app.get("/_test/request-id")
    async def _echo() -> dict[str, str | None]:
        return {"request_id": get_request_id()}

    with TestClient(app) as test_client:
        r = test_client.get("/_test/request-id")

    assert r.status_code == 200
    body = r.json()
    assert body["request_id"] == r.headers["X-Request-ID"]
    assert _HEX64.match(body["request_id"])


def test_each_request_gets_a_new_id(client: TestClient) -> None:
    a = client.get("/healthz").headers["X-Request-ID"]
    b = client.get("/healthz").headers["X-Request-ID"]

    assert a != b
