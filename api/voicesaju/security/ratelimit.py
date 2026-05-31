"""Token-bucket rate limiter (ISSUE-081, NFR-016, OWASP A07).

Strategy — **per-key token bucket**.

- Each route can declare ``rate_limit("auth", "10/min")`` as a FastAPI
  dependency. The dependency derives a bucket key from
  ``(name, identity)`` where ``identity`` is the client IP for
  unauthenticated routes (auth + checkout in Phase-1).
- The backend is a Protocol with two implementations:
  - ``InMemoryRateLimitBackend`` — Phase-1 default; dict + monotonic
    clock + asyncio lock. Single-process only.
  - A Redis-backed implementation will land alongside the Redis
    rollout (ISSUE-100); the route layer requires no changes.
- On limit exceeded the dependency raises ``RateLimitExceeded``, which
  the exception handler installed by ``install_rate_limit`` translates
  into a 429 + ``Retry-After`` header. The exception path is **never**
  taken for backend errors — those fail open with a WARNING log so a
  Redis outage cannot deny service (AC2).

Architecture-Ref: §11.4 (auth strategy table — rate-limit row).
PRD-Ref: NFR-016 (success metrics), OWASP A07 (broken auth).
"""

from __future__ import annotations

import asyncio
import logging
import math
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

from fastapi import FastAPI, Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from starlette.responses import JSONResponse
from starlette.responses import Response as StarletteResponse

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Rate spec parsing
# ---------------------------------------------------------------------------


_UNIT_TO_SECONDS = {
    "sec": 1.0,
    "s": 1.0,
    "min": 60.0,
    "m": 60.0,
    "hour": 3600.0,
    "h": 3600.0,
}

_RATE_RE = re.compile(r"^(?P<limit>\d+)/(?P<unit>[a-zA-Z]+)$")


@dataclass(frozen=True)
class RateSpec:
    """Parsed ``N/unit`` rate."""

    limit: int
    window_seconds: float


def parse_rate(spec: str) -> RateSpec:
    """Parse ``"10/min"`` into a ``RateSpec``.

    Raises ``ValueError`` for malformed inputs so misconfig surfaces at
    import time rather than as a silent zero-rate at runtime.
    """
    m = _RATE_RE.match(spec.strip())
    if not m:
        raise ValueError(f"invalid rate spec: {spec!r}")
    limit = int(m.group("limit"))
    if limit <= 0:
        raise ValueError(f"rate limit must be positive: {spec!r}")
    unit = m.group("unit").lower()
    window = _UNIT_TO_SECONDS.get(unit)
    if window is None:
        raise ValueError(f"unknown rate unit {unit!r} in {spec!r}")
    return RateSpec(limit=limit, window_seconds=window)


# ---------------------------------------------------------------------------
# Result + exception shapes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RateLimitResult:
    """Outcome of a single bucket check.

    ``retry_after_seconds`` is populated only when ``allowed`` is False;
    it is the integer seconds the caller should wait before retrying.
    """

    allowed: bool
    retry_after_seconds: int | None


class RateLimitExceeded(Exception):
    """Raised by the dependency when the bucket is empty.

    Carries ``retry_after_seconds`` so the exception handler can echo it
    into the ``Retry-After`` response header.
    """

    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__(f"rate limit exceeded; retry after {retry_after_seconds}s")
        self.retry_after_seconds = retry_after_seconds


# ---------------------------------------------------------------------------
# Backend protocol + in-memory implementation
# ---------------------------------------------------------------------------


class RateLimitBackend(Protocol):
    """Pluggable backend — in-memory now, Redis later."""

    async def check_and_consume(
        self, key: str, *, limit: int, window_seconds: float
    ) -> RateLimitResult:
        """Consume one token for ``key``; return whether it fit the bucket."""
        ...


@dataclass
class _Bucket:
    tokens: float
    last_refill: float


@dataclass
class InMemoryRateLimitBackend:
    """Single-process token-bucket backend.

    Refill rate = ``limit / window_seconds`` tokens per second. The
    bucket is capped at ``limit`` so a long idle period does not grant
    a burst beyond the spec.
    """

    _buckets: dict[str, _Bucket] = field(default_factory=dict)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def check_and_consume(
        self, key: str, *, limit: int, window_seconds: float
    ) -> RateLimitResult:
        refill_rate = limit / window_seconds
        async with self._lock:
            now = time.monotonic()
            bucket = self._buckets.get(key)
            if bucket is None:
                # Fresh key starts full so the first call always passes.
                bucket = _Bucket(tokens=float(limit), last_refill=now)
                self._buckets[key] = bucket
            else:
                elapsed = max(0.0, now - bucket.last_refill)
                bucket.tokens = min(float(limit), bucket.tokens + elapsed * refill_rate)
                bucket.last_refill = now

            if bucket.tokens >= 1.0:
                bucket.tokens -= 1.0
                return RateLimitResult(allowed=True, retry_after_seconds=None)

            # Not enough — compute how long until 1 token is available.
            deficit = 1.0 - bucket.tokens
            retry_seconds = max(1, math.ceil(deficit / refill_rate))
            # Clamp to the window so the header is never misleading.
            retry_seconds = min(retry_seconds, int(math.ceil(window_seconds)))
            return RateLimitResult(allowed=False, retry_after_seconds=retry_seconds)


# Process-wide singleton; tests reset via ``reset_default_backend_for_tests``.
_default_backend: RateLimitBackend = InMemoryRateLimitBackend()


def get_default_backend() -> RateLimitBackend:
    """Return the active backend (in-memory for Phase-1)."""
    return _default_backend


def reset_default_backend_for_tests() -> None:
    """Wipe + replace the singleton between tests."""
    global _default_backend
    _default_backend = InMemoryRateLimitBackend()


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------


def _client_identity(request: Request) -> str:
    """Best-effort client identifier for rate-limit keys.

    Prefer the left-most entry of ``X-Forwarded-For`` (set by Fly / our
    edge proxy) so a single IP behind NAT cannot evade the limit by
    rotating its socket port. Fall back to the socket peer for local
    dev and tests.
    """
    fwd = request.headers.get("x-forwarded-for") or request.headers.get(
        "X-Forwarded-For"
    )
    if fwd:
        first = fwd.split(",", 1)[0].strip()
        if first:
            return first
    client = request.client
    return client.host if client else "unknown"


def rate_limit(
    name: str,
    spec: str,
    *,
    backend: RateLimitBackend | None = None,
) -> Callable[[Request], object]:
    """Return a FastAPI dependency that enforces ``spec`` for ``name``.

    ``name`` namespaces the bucket so ``rate_limit("auth", ...)`` and
    ``rate_limit("checkout", ...)`` keep independent counters per IP.

    The dependency NEVER raises on backend errors — Redis outages are
    logged at WARNING and the request proceeds (AC2 — fail-open).
    """
    rate = parse_rate(spec)

    async def _dep(request: Request) -> None:
        active_backend = backend if backend is not None else get_default_backend()
        identity = _client_identity(request)
        key = f"{name}:{identity}"
        try:
            result = await active_backend.check_and_consume(
                key, limit=rate.limit, window_seconds=rate.window_seconds
            )
        except Exception as exc:  # noqa: BLE001 — fail-open is the policy
            logger.warning(
                "ratelimit backend error; failing open name=%s key=%s err=%s",
                name,
                identity,
                exc,
            )
            return None

        if not result.allowed:
            # ``retry_after_seconds`` is always set when allowed=False;
            # guard with 1s default for paranoia.
            raise RateLimitExceeded(retry_after_seconds=result.retry_after_seconds or 1)
        return None

    return _dep


# ---------------------------------------------------------------------------
# Exception handler + app wiring
# ---------------------------------------------------------------------------


async def _handle_rate_limit_exceeded(
    _request: Request, exc: Exception
) -> JSONResponse:
    """Translate ``RateLimitExceeded`` into a 429 with ``Retry-After``."""
    assert isinstance(exc, RateLimitExceeded)
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        headers={"Retry-After": str(exc.retry_after_seconds)},
        content={
            "detail": {
                "error": {
                    "code": "rate_limit_exceeded",
                    "message": "rate limit exceeded; retry later",
                    "retry_after_seconds": exc.retry_after_seconds,
                }
            }
        },
    )


def install_rate_limit(app: FastAPI) -> None:
    """Register the 429 exception handler on ``app``.

    The dependency itself is wired per-route; this only needs to run
    once per app so the handler is installed.
    """
    app.add_exception_handler(RateLimitExceeded, _handle_rate_limit_exceeded)


# ---------------------------------------------------------------------------
# Path-based middleware — applies the limit without modifying router files
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _PathRule:
    """Match HTTP method + path prefix → bucket name + spec."""

    methods: frozenset[str]
    prefix: str
    name: str
    spec: RateSpec


def _default_path_rules(*, auth_spec: str, payment_spec: str) -> list[_PathRule]:
    """Architecture §11.4 default coverage — auth + checkout."""
    return [
        _PathRule(
            methods=frozenset({"GET", "POST"}),
            prefix="/api/v1/auth/",
            name="auth",
            spec=parse_rate(auth_spec),
        ),
        _PathRule(
            methods=frozenset({"POST"}),
            prefix="/api/v1/payments/checkout",
            name="checkout",
            spec=parse_rate(payment_spec),
        ),
    ]


class PathRateLimitMiddleware(BaseHTTPMiddleware):
    """Apply path-prefix rate-limit rules in front of every request.

    Rationale: wiring the rate limit at the middleware layer lets us
    cover ``/api/v1/auth/*`` and ``/api/v1/payments/checkout`` without
    editing every router (which would cause cascading test churn).

    Bypass conditions:
    - ``enabled=False`` → middleware short-circuits (staged rollout).
    - No rule matches the request path / method → request proceeds.
    - Backend raises → fail-open WARNING log (AC2 — never deny).
    """

    def __init__(
        self,
        app,
        *,
        enabled: bool = True,
        rules: list[_PathRule] | None = None,
        backend: RateLimitBackend | None = None,
    ) -> None:
        super().__init__(app)
        self.enabled = enabled
        self.rules = rules or []
        self._backend = backend

    @property
    def backend(self) -> RateLimitBackend:
        return self._backend if self._backend is not None else get_default_backend()

    def _match(self, request: StarletteRequest) -> _PathRule | None:
        path = request.url.path
        method = request.method.upper()
        for rule in self.rules:
            if method in rule.methods and path.startswith(rule.prefix):
                return rule
        return None

    async def dispatch(  # type: ignore[override]
        self, request: StarletteRequest, call_next
    ) -> StarletteResponse:
        if not self.enabled:
            return await call_next(request)

        rule = self._match(request)
        if rule is None:
            return await call_next(request)

        identity = _client_identity(request)
        key = f"{rule.name}:{identity}"
        try:
            result = await self.backend.check_and_consume(
                key,
                limit=rule.spec.limit,
                window_seconds=rule.spec.window_seconds,
            )
        except Exception as exc:  # noqa: BLE001 — fail-open is the policy
            logger.warning(
                "ratelimit backend error; failing open rule=%s key=%s err=%s",
                rule.name,
                identity,
                exc,
            )
            return await call_next(request)

        if not result.allowed:
            retry = result.retry_after_seconds or 1
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                headers={"Retry-After": str(retry)},
                content={
                    "detail": {
                        "error": {
                            "code": "rate_limit_exceeded",
                            "message": "rate limit exceeded; retry later",
                            "retry_after_seconds": retry,
                        }
                    }
                },
            )

        return await call_next(request)


def install_path_rate_limit(
    app: FastAPI,
    *,
    enabled: bool = True,
    auth_spec: str = "10/min",
    payment_spec: str = "5/min",
) -> None:
    """Wire path-based rate limiting onto ``app``.

    Defaults match architecture §11.4: 10 req/min per IP for auth,
    5 req/min per IP for payment checkout. The middleware is added in
    a no-op state when ``enabled=False`` so existing tests keep passing
    during the staged rollout.
    """
    rules = _default_path_rules(auth_spec=auth_spec, payment_spec=payment_spec)
    app.add_middleware(
        PathRateLimitMiddleware,
        enabled=enabled,
        rules=rules,
    )


__all__ = [
    "InMemoryRateLimitBackend",
    "PathRateLimitMiddleware",
    "RateLimitBackend",
    "RateLimitExceeded",
    "RateLimitResult",
    "RateSpec",
    "get_default_backend",
    "install_path_rate_limit",
    "install_rate_limit",
    "parse_rate",
    "rate_limit",
    "reset_default_backend_for_tests",
]
