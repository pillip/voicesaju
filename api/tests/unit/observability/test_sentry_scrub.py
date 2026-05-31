"""Unit tests for the Sentry ``before_send`` PII scrubber (ISSUE-078).

Verifies:

1. ``scrub_event`` strips ``birth_dt`` from any depth in the event tree.
2. paymentKey / Toss order IDs / JWTs are stripped from string values.
3. Sensitive dict keys are replaced regardless of value contents.
4. ``init_sentry`` is a no-op when DSN is unset (returns False, no SDK
   state mutation).
5. ``init_sentry`` returns True and configures the SDK when DSN is set,
   without actually firing network traffic (we mock transport).
"""

from __future__ import annotations

from unittest.mock import patch

import sentry_sdk

from voicesaju.observability.sentry import REDACTED, init_sentry, scrub_event


def test_scrub_strips_birth_dt_from_extra() -> None:
    event = {
        "level": "error",
        "message": "saju.compute failed",
        "extra": {"birth_dt": "1989-04-12", "category": "love"},
    }

    cleaned = scrub_event(event, {})

    assert cleaned["extra"]["birth_dt"] == REDACTED
    assert cleaned["extra"]["category"] == "love"


def test_scrub_strips_birth_dt_from_string_message() -> None:
    event = {"message": "user_signup birth_dt=1990-05-01 ok=true"}

    cleaned = scrub_event(event, {})

    assert "1990-05-01" not in cleaned["message"]
    assert REDACTED in cleaned["message"]


def test_scrub_strips_payment_key_from_breadcrumb() -> None:
    event = {
        "breadcrumbs": {
            "values": [
                {
                    "category": "http",
                    "message": (
                        "POST /api/v1/payments/confirm "
                        '{"paymentKey":"live_5g012345abcdefghIJKL","orderId":"ORD-AAA0001"}'
                    ),
                }
            ]
        }
    }

    cleaned = scrub_event(event, {})
    msg = cleaned["breadcrumbs"]["values"][0]["message"]

    assert "live_5g012345abcdefghIJKL" not in msg
    assert "ORD-AAA0001" not in msg
    assert REDACTED in msg


def test_scrub_strips_jwt_from_request_headers() -> None:
    token = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1MTIzIn0.abc-_DEFsig"
    event = {
        "request": {
            "headers": {"Authorization": f"Bearer {token}"},
        }
    }

    cleaned = scrub_event(event, {})

    # `Authorization` is a sensitive dict key → value fully redacted.
    assert cleaned["request"]["headers"]["Authorization"] == REDACTED


def test_scrub_handles_none_and_primitives() -> None:
    event = {
        "level": "error",
        "tags": {"http_status": 500, "ok": True, "ratio": 0.95},
        "extra": {"note": None},
    }

    cleaned = scrub_event(event, {})

    assert cleaned["level"] == "error"
    assert cleaned["tags"]["http_status"] == 500
    assert cleaned["tags"]["ok"] is True
    assert cleaned["tags"]["ratio"] == 0.95
    assert cleaned["extra"]["note"] is None


def test_init_sentry_noop_when_dsn_unset() -> None:
    # Patch sentry_sdk.init so even if something went wrong we'd catch it.
    with patch.object(sentry_sdk, "init") as mock_init:
        result = init_sentry(dsn=None, environment="local")

    assert result is False
    mock_init.assert_not_called()


def test_init_sentry_noop_when_dsn_empty_string() -> None:
    with patch.object(sentry_sdk, "init") as mock_init:
        result = init_sentry(dsn="", environment="local")

    assert result is False
    mock_init.assert_not_called()


def test_init_sentry_calls_sdk_init_when_dsn_set() -> None:
    fake_dsn = "https://abc123@example.ingest.sentry.io/12345"

    with patch.object(sentry_sdk, "init") as mock_init:
        result = init_sentry(
            dsn=fake_dsn,
            environment="staging",
            release="v0.1.0",
            traces_sample_rate=0.05,
        )

    assert result is True
    mock_init.assert_called_once()
    kwargs = mock_init.call_args.kwargs
    assert kwargs["dsn"] == fake_dsn
    assert kwargs["environment"] == "staging"
    assert kwargs["release"] == "v0.1.0"
    assert kwargs["traces_sample_rate"] == 0.05
    assert kwargs["send_default_pii"] is False
    # before_send must be the scrub callback
    assert kwargs["before_send"] is scrub_event


def test_init_sentry_default_traces_sample_rate_is_zero() -> None:
    with patch.object(sentry_sdk, "init") as mock_init:
        init_sentry(dsn="https://x@example.ingest.sentry.io/1")

    kwargs = mock_init.call_args.kwargs
    # Default 0.0 — OTel pipeline is the primary trace backend.
    assert kwargs["traces_sample_rate"] == 0.0
