"""Auth adapter Protocol + concrete implementations.

Phase 1 ships `MockAuthAdapter` which mints an HS256-signed dev JWT for
`test_user_001` so every auth-gated endpoint runs in CI without an OAuth
provider. `KakaoAuthAdapter`, `AppleAuthAdapter`, `TossIdAdapter` are Phase 2
stubs whose methods raise `NotImplementedError` only at call time so the
app still boots under `AUTH_PROVIDER=<provider>` even without credentials.

PRD-Ref: FR-016 (account identity), FR-017 (signup grant idempotency).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal, Protocol

import jwt

from voicesaju.config import Settings, get_settings

# Test fixture identity used by the mock adapter. Kept as constants so
# tests and the seed fixture share the exact same values.
TEST_USER_ID = "test_user_001"
TEST_USER_EMAIL = "test@voicesaju.dev"

# Default lifetime for issued mock tokens. Long enough for full e2e runs
# without forcing the test harness to mint a fresh token mid-run.
MOCK_JWT_TTL_SECONDS = 3600


@dataclass
class AuthSession:
    """Returned by `complete_login()` after an OAuth callback.

    The mock implementation returns the same shape so callers don't need
    to branch on adapter type.
    """

    access_token: str
    token_type: str = "Bearer"
    expires_in: int = MOCK_JWT_TTL_SECONDS


@dataclass
class UserContext:
    """Resolved identity attached to `request.state.user` by the middleware."""

    user_id: str
    email: str
    provider: str = "mock"


@dataclass
class OAuthCallbackUser:
    """Userinfo returned after exchanging an OAuth callback `code`.

    Returned by `resolve_oauth_callback()` so the route handler can hand
    `(provider, subject_id, email)` directly to
    `UserService.find_or_create_by_provider()`. Email may be `None` —
    Apple omits it after the first sign-in, which the dup-detection code
    handles by falling back to the provider subject id.
    """

    subject_id: str
    email: str | None
    provider: Literal["kakao", "apple"]


# Provider literal kept module-level so callers can import it.
Provider = Literal["kakao", "apple"]


class AuthAdapter(Protocol):
    """Provider-agnostic auth client used by the request middleware."""

    def start_login(self) -> str:
        """Return a redirect URL (real providers) or a token (mock)."""
        ...

    def complete_login(self, code: str) -> AuthSession:
        """Exchange an OAuth callback code for an access token."""
        ...

    def verify_token(self, token: str) -> UserContext:
        """Verify a bearer token; raise on invalid/expired."""
        ...

    def resolve_oauth_callback(
        self, provider: Provider, code: str
    ) -> OAuthCallbackUser:
        """Exchange a callback `code` for the resolved (sub, email) userinfo.

        Real providers (ISSUE-025) will perform the token + userinfo HTTP
        roundtrip; the mock returns deterministic synthetic values.
        """
        ...


# ---------------------------------------------------------------------------
# Mock implementation
# ---------------------------------------------------------------------------


class MockAuthAdapter:
    """Deterministic auth adapter for Phase 1 PoC.

    Mints HS256-signed JWTs using `settings.mock_auth_jwt_secret`. The
    issued token carries the seeded test user identity so any middleware
    can resolve `request.state.user` without hitting a real provider.
    """

    JWT_ALGORITHM = "HS256"

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        # Resolve once at construction so middleware can rely on a stable
        # secret across requests (matches how a real adapter would cache
        # JWKS material).
        self._secret = self._settings.mock_auth_jwt_secret

    def start_login(self) -> str:
        """Mint and return a signed JWT (no redirect needed in mock mode)."""
        return self._mint_token()

    def complete_login(self, code: str) -> AuthSession:  # noqa: ARG002
        # Mock ignores the `code` — every call returns a valid session for
        # the seeded test user so e2e flows don't need to manage OAuth state.
        return AuthSession(access_token=self._mint_token())

    def verify_token(self, token: str) -> UserContext:
        payload = jwt.decode(token, self._secret, algorithms=[self.JWT_ALGORITHM])
        return UserContext(
            user_id=payload["sub"],
            email=payload.get("email", TEST_USER_EMAIL),
            provider=payload.get("provider", "mock"),
        )

    def _mint_token(self) -> str:
        now = datetime.now(tz=UTC)
        payload = {
            "sub": TEST_USER_ID,
            "email": TEST_USER_EMAIL,
            "provider": "mock",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=MOCK_JWT_TTL_SECONDS)).timestamp()),
            "iss": "voicesaju-mock-auth",
        }
        return jwt.encode(payload, self._secret, algorithm=self.JWT_ALGORITHM)

    def resolve_oauth_callback(
        self, provider: Provider, code: str
    ) -> OAuthCallbackUser:
        """Return deterministic synthetic userinfo for an OAuth callback.

        Synthesis rules:
        - ``code`` is hashed into a stable per-(provider, code) subject id
          so two callbacks with the same `code` resolve to the same user
          (lets tests exercise the "found by sub" path without managing
          provider state).
        - The synthetic email is derived from the same hash so the
          dup-detection path (two providers, same email) can be exercised
          by passing matching codes across providers.
        - The literal code ``"dup-email-test"`` produces a fixed shared
          email across both providers, so the architecture §11 cross-
          provider linking AC can be tested deterministically.
        """
        if code == "dup-email-test":
            # Shared email across providers — exercises the email_hash link.
            sub = f"{provider}-shared-sub"
            email = "shared@voicesaju.dev"
            return OAuthCallbackUser(subject_id=sub, email=email, provider=provider)
        digest = hashlib.sha256(f"{provider}:{code}".encode()).hexdigest()[:16]
        sub = f"{provider}-{digest}"
        email = f"mock-{digest}@voicesaju.dev"
        return OAuthCallbackUser(subject_id=sub, email=email, provider=provider)


# ---------------------------------------------------------------------------
# Real-provider stubs (Phase 2)
# ---------------------------------------------------------------------------


class _NotImplementedAdapter:
    """Base class for Phase 2 stubs.

    Importing/instantiating must NOT raise so `AUTH_PROVIDER=<provider>`
    can be wired before the real client lands; calls fail loudly with a
    pointer to the follow-up issue.
    """

    _provider_name: str = "<provider>"

    def start_login(self) -> str:
        raise NotImplementedError(
            f"{self._provider_name} adapter is a Phase 2 stub. See ISSUE-025."
        )

    def complete_login(self, code: str) -> AuthSession:
        raise NotImplementedError(
            f"{self._provider_name} adapter is a Phase 2 stub. See ISSUE-025."
        )

    def verify_token(self, token: str) -> UserContext:
        raise NotImplementedError(
            f"{self._provider_name} adapter is a Phase 2 stub. See ISSUE-025."
        )

    def resolve_oauth_callback(
        self, provider: Provider, code: str
    ) -> OAuthCallbackUser:
        raise NotImplementedError(
            f"{self._provider_name} adapter is a Phase 2 stub. See ISSUE-025."
        )


class KakaoAuthAdapter(_NotImplementedAdapter):
    _provider_name = "Kakao"


class AppleAuthAdapter(_NotImplementedAdapter):
    _provider_name = "Apple"


class TossIdAdapter(_NotImplementedAdapter):
    _provider_name = "TossId"


__all__ = [
    "AppleAuthAdapter",
    "AuthAdapter",
    "AuthSession",
    "KakaoAuthAdapter",
    "MOCK_JWT_TTL_SECONDS",
    "MockAuthAdapter",
    "OAuthCallbackUser",
    "Provider",
    "TEST_USER_EMAIL",
    "TEST_USER_ID",
    "TossIdAdapter",
    "UserContext",
]
