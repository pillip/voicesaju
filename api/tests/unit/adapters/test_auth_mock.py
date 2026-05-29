"""Unit tests for MockAuthAdapter + auth adapter factory (ISSUE-100)."""

from __future__ import annotations

import pytest

from voicesaju.adapters import (
    AppleAuthAdapter,
    KakaoAuthAdapter,
    MockAuthAdapter,
    TossIdAdapter,
    UnknownProviderError,
    get_auth_adapter,
)
from voicesaju.adapters.auth import (
    TEST_USER_EMAIL,
    TEST_USER_ID,
    UserContext,
)
from voicesaju.config import Settings


@pytest.fixture
def mock_settings() -> Settings:
    return Settings(
        environment="local",
        auth_provider="mock",
        mock_auth_jwt_secret="unit-test-secret-1234567890",
    )


def test_factory_returns_mock_when_provider_is_mock(mock_settings: Settings) -> None:
    adapter = get_auth_adapter(mock_settings)
    assert isinstance(adapter, MockAuthAdapter)


def test_factory_returns_stub_for_real_providers() -> None:
    for provider_name, klass in [
        ("kakao", KakaoAuthAdapter),
        ("apple", AppleAuthAdapter),
        ("toss_id", TossIdAdapter),
    ]:
        settings = Settings(
            environment="local",
            auth_provider=provider_name,  # type: ignore[arg-type]
        )
        adapter = get_auth_adapter(settings)
        assert isinstance(adapter, klass)


def test_factory_raises_on_unknown_provider() -> None:
    settings = Settings(environment="local")
    # Bypass Literal validation by mutating after construction.
    object.__setattr__(settings, "auth_provider", "unknown")
    with pytest.raises(UnknownProviderError):
        get_auth_adapter(settings)


def test_mock_start_login_returns_signed_jwt(mock_settings: Settings) -> None:
    adapter = MockAuthAdapter(settings=mock_settings)
    token = adapter.start_login()
    assert isinstance(token, str) and token.count(".") == 2  # header.payload.sig


def test_mock_verify_roundtrip(mock_settings: Settings) -> None:
    adapter = MockAuthAdapter(settings=mock_settings)
    token = adapter.start_login()
    user = adapter.verify_token(token)
    assert isinstance(user, UserContext)
    assert user.user_id == TEST_USER_ID
    assert user.email == TEST_USER_EMAIL
    assert user.provider == "mock"


def test_mock_complete_login_returns_session(mock_settings: Settings) -> None:
    adapter = MockAuthAdapter(settings=mock_settings)
    session = adapter.complete_login(code="ignored-by-mock")
    assert session.token_type == "Bearer"
    assert session.expires_in > 0
    # Token must be verifiable by the same adapter.
    user = adapter.verify_token(session.access_token)
    assert user.user_id == TEST_USER_ID


def test_mock_verify_rejects_tampered_token(mock_settings: Settings) -> None:
    import jwt as pyjwt

    adapter = MockAuthAdapter(settings=mock_settings)
    token = adapter.start_login()
    # Flip a character in the signature segment.
    head, payload, sig = token.split(".")
    tampered = ".".join([head, payload, sig[:-1] + ("A" if sig[-1] != "A" else "B")])
    with pytest.raises(pyjwt.exceptions.InvalidSignatureError):
        adapter.verify_token(tampered)


def test_kakao_stub_raises_at_call_time_only() -> None:
    # Instantiation must NOT raise so the app boots; only calls fail.
    stub = KakaoAuthAdapter()
    with pytest.raises(NotImplementedError):
        stub.start_login()


def test_production_blocks_mock_auth() -> None:
    """ENVIRONMENT=prod + AUTH_PROVIDER=mock must raise at construction."""
    with pytest.raises(ValueError, match="AUTH_PROVIDER=mock"):
        Settings(
            environment="prod",
            auth_provider="mock",
            mock_auth_jwt_secret="x" * 32,
        )
