"""Integration test for the full mock payment flow.

Exercises the live `/api/payments/checkout` endpoint with the
`MockPaymentAdapter` wired through FastAPI's BackgroundTasks runner, then
asserts the simulated webhook recorded a `succeeded` confirmation after
the configured delay.

The 3-second default delay is patched down to 0 via
`MOCK_WEBHOOK_DELAY_SECONDS` to keep CI fast — the real delay is
covered by the dedicated freeze-clock unit test.

Marked `integration` because it spins up the full TestClient
(BackgroundTasks runner + lifespan) rather than calling adapter methods
directly.
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from voicesaju.adapters import payment as payment_module
from voicesaju.adapters.payment import MockPaymentAdapter
from voicesaju.main import create_app

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _patch_delay_and_reset(monkeypatch: pytest.MonkeyPatch) -> None:
    # Run webhook synchronously by collapsing the simulated delay to 0;
    # we still go through asyncio.sleep so the code path matches prod.
    monkeypatch.setattr(payment_module, "MOCK_WEBHOOK_DELAY_SECONDS", 0.0)
    MockPaymentAdapter.reset()


def test_full_checkout_to_succeeded() -> None:
    app = create_app()
    with TestClient(app) as client:
        response = client.post(
            "/api/payments/checkout",
            json={
                "user_id": "u-integration",
                "kind": "single",
                "amount_krw": 4900,
                "idempotency_key": "int-1",
            },
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["redirect_url"] == "#mock-success"
    assert body["amount_krw"] == 4900
    assert body["kind"] == "single"
    session_id = body["session_id"]

    # BackgroundTasks ran during the TestClient `with` block; the webhook
    # has already written the succeeded confirmation into the in-process
    # registry by the time we exit the context manager.
    adapter = MockPaymentAdapter()
    confirmation = asyncio.run(adapter.confirm_payment(session_id))
    assert confirmation.status == "succeeded"
    assert confirmation.amount_krw == 4900


def test_webhook_endpoint_accepts_payload() -> None:
    """The internal webhook endpoint must 200 with a well-formed payload."""
    app = create_app()
    with TestClient(app) as client:
        response = client.post(
            "/api/payments/webhook",
            json={
                "session_id": "mock-test",
                "status": "succeeded",
                "amount_krw": 4900,
            },
        )
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
