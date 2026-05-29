"""Route-level tests for `POST /api/v1/auth/device` (ISSUE-024).

Exercises the FastAPI route with an in-memory SQLite session injected
via dependency override. Verifies:
- Successful upsert + ``vs_did`` cookie attributes (HttpOnly, Secure,
  SameSite=Lax, Max-Age=1y).
- Idempotency at the HTTP layer.
- Pydantic 422 on non-UUID input.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Iterator

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from voicesaju.db.base import Base
from voicesaju.db.engine import get_session
from voicesaju.db.models import Device  # noqa: F401 - register metadata
from voicesaju.main import create_app


@pytest_asyncio.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest.fixture
def client(engine: AsyncEngine) -> Iterator[TestClient]:
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def _override_get_session() -> AsyncIterator[AsyncSession]:
        async with maker() as s:
            yield s

    app = create_app()
    app.dependency_overrides[get_session] = _override_get_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _post_device(client: TestClient, *, device_id_client: str) -> object:
    return client.post(
        "/api/v1/auth/device",
        json={"device_id_client": device_id_client},
    )


def test_first_call_returns_200_with_device_id_and_cookie(
    client: TestClient,
) -> None:
    client_id = str(uuid.uuid4())
    resp = _post_device(client, device_id_client=client_id)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "device_id" in body
    server_id = body["device_id"]
    # uuidv7 string is a valid UUID.
    assert uuid.UUID(server_id)
    # Server id is NOT the client-supplied uuid.
    assert server_id != client_id

    # Cookie header carries vs_did with the server-side id.
    set_cookie = resp.headers.get("set-cookie", "")
    assert "vs_did=" in set_cookie
    assert server_id in set_cookie


def test_set_cookie_has_required_security_attributes(
    client: TestClient,
) -> None:
    """AC: ``HttpOnly``, ``Secure``, ``SameSite=Lax``, 1-year expiry."""
    client_id = str(uuid.uuid4())
    resp = _post_device(client, device_id_client=client_id)

    set_cookie = resp.headers.get("set-cookie", "").lower()
    assert "httponly" in set_cookie
    assert "secure" in set_cookie
    assert "samesite=lax" in set_cookie
    # 365 days in seconds = 31_536_000.
    assert "max-age=31536000" in set_cookie


def test_second_call_with_same_client_id_returns_same_server_id(
    client: TestClient,
) -> None:
    """AC: same ``device_id_client`` → existing row reused (no duplicate)."""
    client_id = str(uuid.uuid4())
    first = _post_device(client, device_id_client=client_id)
    second = _post_device(client, device_id_client=client_id)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["device_id"] == second.json()["device_id"]


def test_invalid_uuid_returns_422(client: TestClient) -> None:
    """AC: non-UUID ``device_id_client`` → 422."""
    resp = client.post(
        "/api/v1/auth/device",
        json={"device_id_client": "not-a-uuid"},
    )
    assert resp.status_code == 422


def test_missing_body_returns_422(client: TestClient) -> None:
    resp = client.post("/api/v1/auth/device", json={})
    assert resp.status_code == 422


def test_response_device_id_matches_cookie_value(
    client: TestClient,
) -> None:
    """The ``device_id`` returned in the body MUST equal the ``vs_did``
    cookie value — clients can compare the two as a defence-in-depth
    integrity check.
    """
    client_id = str(uuid.uuid4())
    resp = _post_device(client, device_id_client=client_id)

    body_id = resp.json()["device_id"]
    # TestClient parses the cookie into the jar — read it back.
    cookie = resp.cookies.get("vs_did")
    assert cookie == body_id
