"""Unit tests for ``voicesaju.observability.logging.redact`` (ISSUE-079).

Covers the four PII pattern families from architecture §12.1:

- ``birth_dt`` ISO-8601 values
- Toss order IDs
- Toss paymentKey values
- JWT bearer tokens

And the sensitive-key dictionary scrubbing path.
"""

from __future__ import annotations

from voicesaju.observability.logging import REDACTED, redact


def test_redact_replaces_sensitive_dict_keys() -> None:
    raw = {
        "user_id": "u_123",
        "birth_dt": "1989-04-12",
        "payment_key": "live_5gd1234",
        "card_number": "4111-1111-1111-1111",
        "access_token": "ey...",
    }

    cleaned = redact(raw)

    assert cleaned["user_id"] == "u_123"
    assert cleaned["birth_dt"] == REDACTED
    assert cleaned["payment_key"] == REDACTED
    assert cleaned["card_number"] == REDACTED
    assert cleaned["access_token"] == REDACTED


def test_redact_strips_birth_dt_in_string() -> None:
    msg = "saju.compute birth_dt=1989-04-12T03:30 category=love"

    cleaned = redact(msg)

    assert "1989-04-12" not in cleaned
    assert REDACTED in cleaned
    assert "category=love" in cleaned


def test_redact_strips_toss_order_id() -> None:
    msg = "payment.checkout orderId=ORD-XQ91A4S2 amount=4900"

    cleaned = redact(msg)

    assert "ORD-XQ91A4S2" not in cleaned
    assert REDACTED in cleaned
    assert "amount=4900" in cleaned


def test_redact_strips_payment_key() -> None:
    msg = 'webhook.body {"paymentKey":"live_5g012345abcdefghIJKLmn","amount":4900}'

    cleaned = redact(msg)

    assert "live_5g012345abcdefghIJKLmn" not in cleaned
    assert REDACTED in cleaned
    # JSON shape preserved
    assert '"amount":4900' in cleaned


def test_redact_strips_jwt_token() -> None:
    token = (
        "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1MTIzIiwiZXhwIjoxOTk5OTk5OTk5fQ.abc123-_DEFsig"
    )
    msg = f"auth.failed bearer={token} route=/api/v1/me"

    cleaned = redact(msg)

    assert token not in cleaned
    assert REDACTED in cleaned
    assert "route=/api/v1/me" in cleaned


def test_redact_recurses_into_nested_structures() -> None:
    raw = {
        "event": "payment.confirm",
        "body": {
            "paymentKey": "live_5g012345abcdefghIJKLmn",
            "orderId": "ORD-AAA0001",
            "amount": 9_900,
        },
        "tags": ["birth_dt=1990-01-01", "ok"],
    }

    cleaned = redact(raw)

    assert cleaned["event"] == "payment.confirm"
    # paymentKey value redacted in JSON-ish string within string? No —
    # the key itself is a dict key, not a sensitive-keys match (case
    # differs). It IS matched by the regex however since the value is
    # a long alnum string adjacent to "paymentKey" in the dump. Since
    # we're inside a dict, the key lookup runs first; "paymentKey"
    # lowercased is "paymentkey" which IS a sensitive key.
    assert cleaned["body"]["paymentKey"] == REDACTED
    # orderId is NOT a sensitive key on its own but the value matches
    # the ORD- prefix regex when redact is applied to the string value.
    assert cleaned["body"]["orderId"] == REDACTED
    assert cleaned["body"]["amount"] == 9_900
    # First tag had a birth_dt= pattern → regex catches it.
    assert REDACTED in cleaned["tags"][0]
    assert cleaned["tags"][1] == "ok"


def test_redact_passes_through_numbers_and_none() -> None:
    assert redact(123) == 123
    assert redact(1.5) == 1.5
    assert redact(None) is None
    assert redact(True) is True
    assert redact(False) is False
    assert redact(b"\x00\x01") == b"\x00\x01"


def test_redact_preserves_list_type() -> None:
    cleaned = redact(["safe", "birth_dt=2000-01-01"])

    assert isinstance(cleaned, list)
    assert cleaned[0] == "safe"
    assert REDACTED in cleaned[1]


def test_redact_preserves_tuple_type() -> None:
    cleaned = redact(("a", "b"))

    assert isinstance(cleaned, tuple)
    assert cleaned == ("a", "b")


def test_redact_handles_case_insensitive_sensitive_keys() -> None:
    raw = {"Birth_DT": "2000-01-01", "PaymentKey": "live_xxx"}

    cleaned = redact(raw)

    assert cleaned["Birth_DT"] == REDACTED
    assert cleaned["PaymentKey"] == REDACTED
