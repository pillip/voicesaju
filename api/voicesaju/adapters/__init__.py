"""Adapter factories.

Adapter selection is driven by `Settings` env vars (e.g. `PAYMENT_PROVIDER`)
so tests, local-dev and prod each get the right backend without code changes.
The Phase 1 PoC stack runs entirely on `*_PROVIDER=mock` so the full vertical
slice exercises without external API credentials (see ISSUE-099..102).
"""

from __future__ import annotations

from voicesaju.adapters.auth import (
    AppleAuthAdapter,
    AuthAdapter,
    KakaoAuthAdapter,
    MockAuthAdapter,
    TossIdAdapter,
)
from voicesaju.adapters.llm import (
    ClaudeAdapter,
    LLMAdapter,
    MockLLMAdapter,
)
from voicesaju.adapters.payment import (
    MockPaymentAdapter,
    PaymentAdapter,
    TossPaymentAdapter,
)
from voicesaju.adapters.tts import (
    MockTTSAdapter,
    SupertoneAdapter,
    TTSAdapter,
)
from voicesaju.config import Settings, get_settings


class UnknownProviderError(RuntimeError):
    """Raised when the configured provider name is not recognised."""


def get_auth_adapter(settings: Settings | None = None) -> AuthAdapter:
    """Return the active auth adapter selected by `settings.auth_provider`.

    Phase 1 default is `mock`. The real-provider stubs instantiate cleanly
    so the app can boot when env points at them but raise
    `NotImplementedError` on the first business-logic call.
    """
    settings = settings or get_settings()
    provider = settings.auth_provider.lower()
    if provider == "mock":
        return MockAuthAdapter(settings=settings)
    if provider == "kakao":
        return KakaoAuthAdapter()
    if provider == "apple":
        return AppleAuthAdapter()
    if provider == "toss_id":
        return TossIdAdapter()
    raise UnknownProviderError(
        f"unknown AUTH_PROVIDER={settings.auth_provider!r}; "
        "expected one of: 'mock', 'kakao', 'apple', 'toss_id'"
    )


def get_llm_adapter(settings: Settings | None = None) -> LLMAdapter:
    """Return the active LLM adapter selected by `settings.llm_provider`.

    Phase 1 default is `mock`. `claude` returns the Phase 2 stub whose
    `stream()` raises ``NotImplementedError`` so the app still boots
    under `LLM_PROVIDER=claude` before ISSUE-035 lands.
    """
    settings = settings or get_settings()
    provider = settings.llm_provider.lower()
    if provider == "mock":
        return MockLLMAdapter()
    if provider == "claude":
        return ClaudeAdapter()
    raise UnknownProviderError(
        f"unknown LLM_PROVIDER={settings.llm_provider!r}; "
        "expected one of: 'mock', 'claude'"
    )


def get_payment_adapter(settings: Settings | None = None) -> PaymentAdapter:
    """Return the active payment adapter selected by `settings.payment_provider`.

    Phase 1 default is `mock`. `toss` returns a stub whose methods raise
    `NotImplementedError` only on first call so the app still boots when the
    env points at a real provider but credentials are missing.
    """
    settings = settings or get_settings()
    provider = settings.payment_provider.lower()
    if provider == "mock":
        return MockPaymentAdapter()
    if provider == "toss":
        return TossPaymentAdapter()
    raise UnknownProviderError(
        f"unknown PAYMENT_PROVIDER={settings.payment_provider!r}; "
        "expected one of: 'mock', 'toss'"
    )


def get_tts_adapter(settings: Settings | None = None) -> TTSAdapter:
    """Return the active TTS adapter selected by `settings.tts_provider`.

    Phase 1 default is `mock`. `supertone` returns the Phase 2 stub whose
    `stream()` raises ``NotImplementedError`` so the app still boots
    under `TTS_PROVIDER=supertone` before ISSUE-036 lands.
    """
    settings = settings or get_settings()
    provider = settings.tts_provider.lower()
    if provider == "mock":
        return MockTTSAdapter()
    if provider == "supertone":
        return SupertoneAdapter()
    raise UnknownProviderError(
        f"unknown TTS_PROVIDER={settings.tts_provider!r}; "
        "expected one of: 'mock', 'supertone'"
    )


__all__ = [
    "AppleAuthAdapter",
    "AuthAdapter",
    "ClaudeAdapter",
    "KakaoAuthAdapter",
    "LLMAdapter",
    "MockAuthAdapter",
    "MockLLMAdapter",
    "MockPaymentAdapter",
    "MockTTSAdapter",
    "PaymentAdapter",
    "SupertoneAdapter",
    "TTSAdapter",
    "TossIdAdapter",
    "TossPaymentAdapter",
    "UnknownProviderError",
    "get_auth_adapter",
    "get_llm_adapter",
    "get_payment_adapter",
    "get_tts_adapter",
]
