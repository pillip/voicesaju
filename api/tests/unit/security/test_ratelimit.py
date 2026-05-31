"""Unit tests for the rate-limit middleware (ISSUE-081).

PRD-Ref: NFR-016, OWASP A07.
Architecture-Ref: §11.4 — token-bucket rate limiter applied to auth
(``10/min`` per IP) and payment checkout (``5/min`` per user). Redis-
backed in production with an in-memory fallback for Phase-1 dev/CI.
Fail-open on Redis errors so a backend outage cannot deny service.
"""

from __future__ import annotations

import logging

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from voicesaju.security.ratelimit import (
    InMemoryRateLimitBackend,
    RateLimitBackend,
    RateLimitExceeded,
    RateLimitResult,
    install_path_rate_limit,
    install_rate_limit,
    parse_rate,
    rate_limit,
    reset_default_backend_for_tests,
)

# ---------------------------------------------------------------------------
# Time control — the in-memory backend reads ``time.monotonic`` directly so
# tests can fast-forward without sleeping.
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_time(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    now = [1000.0]

    def _now() -> float:
        return now[0]

    monkeypatch.setattr("voicesaju.security.ratelimit.time.monotonic", _now)
    return now


@pytest.fixture(autouse=True)
def _reset_backend() -> None:
    reset_default_backend_for_tests()


# ---------------------------------------------------------------------------
# parse_rate
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "spec,limit,window",
    [
        ("10/min", 10, 60.0),
        ("5/min", 5, 60.0),
        ("100/hour", 100, 3600.0),
        ("3/sec", 3, 1.0),
        ("1/s", 1, 1.0),
    ],
)
def test_parse_rate_valid(spec: str, limit: int, window: float) -> None:
    """``N/unit`` strings parse into (limit, window-seconds) pairs."""
    parsed = parse_rate(spec)
    assert parsed.limit == limit
    assert parsed.window_seconds == window


@pytest.mark.parametrize("spec", ["bad", "10", "10/", "/min", "abc/min", "10/day"])
def test_parse_rate_invalid_raises(spec: str) -> None:
    """Malformed specs raise ``ValueError`` so misconfig surfaces early."""
    with pytest.raises(ValueError):
        parse_rate(spec)


# ---------------------------------------------------------------------------
# InMemoryRateLimitBackend — token bucket
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_in_memory_backend_allows_requests_under_limit(
    fake_time: list[float],
) -> None:
    """First N requests fit the bucket and return ``allowed=True``."""
    backend = InMemoryRateLimitBackend()
    for _ in range(10):
        result = await backend.check_and_consume("key", limit=10, window_seconds=60)
        assert result.allowed is True


@pytest.mark.asyncio
async def test_in_memory_backend_blocks_when_bucket_empty(
    fake_time: list[float],
) -> None:
    """Once the bucket is drained the 11th request is denied with retry_after."""
    backend = InMemoryRateLimitBackend()
    for _ in range(10):
        await backend.check_and_consume("key", limit=10, window_seconds=60)

    result = await backend.check_and_consume("key", limit=10, window_seconds=60)
    assert result.allowed is False
    assert result.retry_after_seconds is not None
    assert result.retry_after_seconds > 0


@pytest.mark.asyncio
async def test_in_memory_backend_refills_over_time(fake_time: list[float]) -> None:
    """Tokens refill linearly — after window/limit seconds we get 1 more."""
    backend = InMemoryRateLimitBackend()
    for _ in range(10):
        await backend.check_and_consume("key", limit=10, window_seconds=60)
    # Empty bucket → blocked
    assert (
        await backend.check_and_consume("key", limit=10, window_seconds=60)
    ).allowed is False

    # Advance 6 seconds: 60/10 = 6s per token, so one fresh slot.
    fake_time[0] += 6.0
    assert (
        await backend.check_and_consume("key", limit=10, window_seconds=60)
    ).allowed is True
    # Bucket is empty again immediately.
    assert (
        await backend.check_and_consume("key", limit=10, window_seconds=60)
    ).allowed is False


@pytest.mark.asyncio
async def test_in_memory_backend_isolates_keys(fake_time: list[float]) -> None:
    """Different keys (e.g. IPs) consume independent buckets."""
    backend = InMemoryRateLimitBackend()
    for _ in range(10):
        await backend.check_and_consume("ip-a", limit=10, window_seconds=60)
    # ip-a drained but ip-b is fresh.
    assert (
        await backend.check_and_consume("ip-b", limit=10, window_seconds=60)
    ).allowed is True
    assert (
        await backend.check_and_consume("ip-a", limit=10, window_seconds=60)
    ).allowed is False


# ---------------------------------------------------------------------------
# rate_limit() FastAPI dependency
# ---------------------------------------------------------------------------


def _make_app(rate_spec: str = "10/min") -> FastAPI:
    app = FastAPI()
    install_rate_limit(app)

    @app.get("/auth", dependencies=[Depends(rate_limit("auth", rate_spec))])
    async def auth_endpoint() -> dict[str, str]:
        return {"status": "ok"}

    return app


def test_dependency_allows_requests_under_limit() -> None:
    """The first ``limit`` requests pass; rate is per-IP via ``X-Forwarded-For``."""
    app = _make_app()
    client = TestClient(app)
    for i in range(10):
        resp = client.get("/auth", headers={"X-Forwarded-For": "203.0.113.5"})
        assert resp.status_code == 200, f"iteration {i}: {resp.text}"


def test_dependency_returns_429_with_retry_after_header() -> None:
    """AC1: 11th request → 429 + ``Retry-After`` header populated."""
    app = _make_app()
    client = TestClient(app)
    for _ in range(10):
        client.get("/auth", headers={"X-Forwarded-For": "203.0.113.5"})

    resp = client.get("/auth", headers={"X-Forwarded-For": "203.0.113.5"})
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers
    # Numeric seconds, in [1, window]
    retry_after = int(resp.headers["Retry-After"])
    assert 1 <= retry_after <= 60
    body = resp.json()
    assert body["detail"]["error"]["code"] == "rate_limit_exceeded"


def test_dependency_isolates_different_ips() -> None:
    """Two distinct IPs each get their own bucket."""
    app = _make_app()
    client = TestClient(app)
    # Drain IP A
    for _ in range(10):
        client.get("/auth", headers={"X-Forwarded-For": "203.0.113.5"})
    # IP B should still be fresh.
    resp = client.get("/auth", headers={"X-Forwarded-For": "198.51.100.7"})
    assert resp.status_code == 200


def test_dependency_falls_back_to_client_host() -> None:
    """When ``X-Forwarded-For`` is absent, the bucket key uses the socket peer."""
    app = _make_app()
    client = TestClient(app)
    # TestClient sets a deterministic remote — exercising the fallback path.
    for _ in range(10):
        client.get("/auth")
    resp = client.get("/auth")
    assert resp.status_code == 429


# ---------------------------------------------------------------------------
# Fail-open on backend error — AC2
# ---------------------------------------------------------------------------


class _BrokenBackend:
    """Backend that always raises — simulates Redis outage."""

    async def check_and_consume(self, key, limit, window_seconds):  # type: ignore[no-untyped-def]
        raise RuntimeError("redis: connection refused")


def test_dependency_fails_open_on_backend_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """AC2: backend raise → request proceeds + WARNING log (never deny)."""
    from voicesaju.security import ratelimit as rl

    app = FastAPI()

    @app.get(
        "/auth",
        dependencies=[
            Depends(rl.rate_limit("auth", "10/min", backend=_BrokenBackend()))
        ],
    )
    async def auth_endpoint() -> dict[str, str]:
        return {"status": "ok"}

    client = TestClient(app)
    caplog.set_level(logging.WARNING)
    resp = client.get("/auth", headers={"X-Forwarded-For": "1.2.3.4"})
    assert resp.status_code == 200, resp.text
    # Warning was emitted on the fail-open path.
    warns = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert any(
        "ratelimit" in (r.message or "").lower() or "rate" in (r.name or "").lower()
        for r in warns
    ), f"Expected WARNING log; got {[r.message for r in warns]}"


# ---------------------------------------------------------------------------
# Exception shape
# ---------------------------------------------------------------------------


def test_rate_limit_exceeded_carries_retry_after() -> None:
    """``RateLimitExceeded`` exposes ``retry_after_seconds`` for the handler."""
    exc = RateLimitExceeded(retry_after_seconds=42)
    assert exc.retry_after_seconds == 42


# ---------------------------------------------------------------------------
# Result helper
# ---------------------------------------------------------------------------


def test_rate_limit_result_is_a_value_object() -> None:
    """``RateLimitResult`` is a plain dataclass-like with ``allowed`` + retry."""
    r = RateLimitResult(allowed=True, retry_after_seconds=None)
    assert r.allowed is True
    assert r.retry_after_seconds is None

    r2 = RateLimitResult(allowed=False, retry_after_seconds=5)
    assert r2.allowed is False
    assert r2.retry_after_seconds == 5


# ---------------------------------------------------------------------------
# Backend protocol check
# ---------------------------------------------------------------------------


def test_in_memory_backend_implements_protocol() -> None:
    """``InMemoryRateLimitBackend`` satisfies ``RateLimitBackend``."""
    backend: RateLimitBackend = InMemoryRateLimitBackend()
    assert backend is not None


# ---------------------------------------------------------------------------
# Per-route key namespacing
# ---------------------------------------------------------------------------


def test_dependency_namespaces_keys_by_route_name() -> None:
    """Two different ``name`` values keep independent buckets per IP."""
    app = FastAPI()
    install_rate_limit(app)

    @app.get("/a", dependencies=[Depends(rate_limit("route-a", "2/min"))])
    async def a() -> dict[str, str]:
        return {"r": "a"}

    @app.get("/b", dependencies=[Depends(rate_limit("route-b", "2/min"))])
    async def b() -> dict[str, str]:
        return {"r": "b"}

    client = TestClient(app)
    hdr = {"X-Forwarded-For": "9.9.9.9"}
    assert client.get("/a", headers=hdr).status_code == 200
    assert client.get("/a", headers=hdr).status_code == 200
    # /a drained
    assert client.get("/a", headers=hdr).status_code == 429
    # /b still fresh
    assert client.get("/b", headers=hdr).status_code == 200


# ---------------------------------------------------------------------------
# Path-based middleware (install_path_rate_limit)
# ---------------------------------------------------------------------------


def _make_path_app(enabled: bool = True) -> FastAPI:
    app = FastAPI()
    install_path_rate_limit(
        app, enabled=enabled, auth_spec="10/min", payment_spec="5/min"
    )

    @app.get("/api/v1/auth/kakao/start")
    async def auth_start() -> dict[str, str]:
        return {"r": "auth"}

    @app.post("/api/v1/payments/checkout")
    async def checkout() -> dict[str, str]:
        return {"r": "checkout"}

    @app.get("/api/v1/me")
    async def me_endpoint() -> dict[str, str]:
        return {"r": "me"}

    return app


def test_install_path_rate_limit_disabled_short_circuits() -> None:
    """``enabled=False`` lets all requests through unconditionally."""
    app = _make_path_app(enabled=False)
    client = TestClient(app)
    # 50 hits to auth without a 429
    for _ in range(50):
        resp = client.get(
            "/api/v1/auth/kakao/start", headers={"X-Forwarded-For": "5.5.5.5"}
        )
        assert resp.status_code == 200


def test_install_path_rate_limit_enforces_auth_default_10_per_min() -> None:
    """AC1: 11th auth request per IP → 429 + Retry-After."""
    app = _make_path_app(enabled=True)
    client = TestClient(app)
    headers = {"X-Forwarded-For": "10.0.0.1"}
    for _ in range(10):
        assert (
            client.get("/api/v1/auth/kakao/start", headers=headers).status_code == 200
        )
    resp = client.get("/api/v1/auth/kakao/start", headers=headers)
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers
    assert int(resp.headers["Retry-After"]) >= 1


def test_install_path_rate_limit_enforces_checkout_default_5_per_min() -> None:
    """Checkout uses the tighter 5/min spec from architecture §11.4."""
    app = _make_path_app(enabled=True)
    client = TestClient(app)
    headers = {"X-Forwarded-For": "10.0.0.2"}
    for _ in range(5):
        assert (
            client.post("/api/v1/payments/checkout", headers=headers).status_code == 200
        )
    resp = client.post("/api/v1/payments/checkout", headers=headers)
    assert resp.status_code == 429


def test_install_path_rate_limit_ignores_unmatched_routes() -> None:
    """``/api/v1/me`` is not in the rule set — no limit applied."""
    app = _make_path_app(enabled=True)
    client = TestClient(app)
    headers = {"X-Forwarded-For": "10.0.0.3"}
    for _ in range(50):
        resp = client.get("/api/v1/me", headers=headers)
        assert resp.status_code == 200


def test_install_path_rate_limit_fails_open_on_backend_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """AC2: backend raises → request proceeds + WARNING log."""
    from voicesaju.security.ratelimit import (
        PathRateLimitMiddleware,
        _default_path_rules,
    )

    app = FastAPI()
    app.add_middleware(
        PathRateLimitMiddleware,
        enabled=True,
        rules=_default_path_rules(auth_spec="10/min", payment_spec="5/min"),
        backend=_BrokenBackend(),
    )

    @app.get("/api/v1/auth/kakao/start")
    async def auth_start() -> dict[str, str]:
        return {"r": "auth"}

    client = TestClient(app)
    caplog.set_level(logging.WARNING)
    resp = client.get(
        "/api/v1/auth/kakao/start", headers={"X-Forwarded-For": "7.7.7.7"}
    )
    assert resp.status_code == 200
    warns = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert any(
        "ratelimit" in (r.message or "").lower() for r in warns
    ), f"Expected WARNING; got {[r.message for r in warns]}"
