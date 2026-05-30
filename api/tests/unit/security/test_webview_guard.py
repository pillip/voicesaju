"""Unit tests for the WebView origin allowlist guard (ISSUE-046).

The guard decides whether an incoming request from a Toss WebView is
allowed to receive a ``SameSite=None; Secure`` session cookie. Only
origins on the allowlist (default ``["https://m.tosspayments.com"]``)
get the relaxed cookie attributes; everything else is rejected with 403.

The unit suite hits the helper directly so the policy is exercised
without spinning up a FastAPI request.
"""

from __future__ import annotations

import pytest

from voicesaju.security.webview_guard import (
    is_allowed_webview_origin,
    normalize_origin,
)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("https://m.tosspayments.com", "https://m.tosspayments.com"),
        ("https://m.tosspayments.com/", "https://m.tosspayments.com"),
        ("https://M.TossPayments.com", "https://m.tosspayments.com"),
        ("https://m.tosspayments.com:443", "https://m.tosspayments.com:443"),
        ("", ""),
    ],
)
def test_normalize_origin(raw: str, expected: str) -> None:
    assert normalize_origin(raw) == expected


def test_allowed_origin_default_list() -> None:
    """Default allowlist accepts the documented Toss WebView origin."""
    assert (
        is_allowed_webview_origin(
            "https://m.tosspayments.com",
            allowlist=["https://m.tosspayments.com"],
        )
        is True
    )


def test_allowed_origin_case_insensitive() -> None:
    assert (
        is_allowed_webview_origin(
            "https://M.TossPayments.COM",
            allowlist=["https://m.tosspayments.com"],
        )
        is True
    )


def test_allowed_origin_trailing_slash_tolerated() -> None:
    assert (
        is_allowed_webview_origin(
            "https://m.tosspayments.com/",
            allowlist=["https://m.tosspayments.com"],
        )
        is True
    )


def test_disallowed_origin_unknown_host() -> None:
    """An origin not in the allowlist must be rejected (AC3)."""
    assert (
        is_allowed_webview_origin(
            "https://evil.example.com",
            allowlist=["https://m.tosspayments.com"],
        )
        is False
    )


def test_disallowed_origin_subdomain_not_matched() -> None:
    """The allowlist does NOT subtree-match — only exact origin matches."""
    assert (
        is_allowed_webview_origin(
            "https://attacker.m.tosspayments.com",
            allowlist=["https://m.tosspayments.com"],
        )
        is False
    )


def test_disallowed_origin_empty_string() -> None:
    """A missing/empty Origin header must be rejected."""
    assert (
        is_allowed_webview_origin(
            "",
            allowlist=["https://m.tosspayments.com"],
        )
        is False
    )


def test_disallowed_origin_http_scheme() -> None:
    """Insecure http:// origin is rejected even if host matches.

    SameSite=None cookies require Secure → an http origin can never get
    one, so we reject at the guard layer rather than letting the cookie
    fall through and be silently dropped by the browser.
    """
    assert (
        is_allowed_webview_origin(
            "http://m.tosspayments.com",
            allowlist=["https://m.tosspayments.com"],
        )
        is False
    )


def test_empty_allowlist_rejects_everything() -> None:
    """A misconfigured deploy (empty allowlist) must reject every origin."""
    assert (
        is_allowed_webview_origin("https://m.tosspayments.com", allowlist=[]) is False
    )
