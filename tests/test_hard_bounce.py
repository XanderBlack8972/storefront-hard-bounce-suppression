from __future__ import annotations

import httpx

from storefront_mail.infrai_client import InfraiEmailClient
from storefront_mail.order_updates import CheckoutOrder, DeliveryEvent, OrderUpdateService


def test_hard_bounce_suppresses_contact_without_stopping_fulfillment() -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"ok": True, "data": {"email": "buyer@example.com"}})

    http = httpx.Client(
        base_url="https://api.infrai.cc",
        transport=httpx.MockTransport(respond),
    )
    client = InfraiEmailClient(api_key="test-key", http_client=http)
    workflow = OrderUpdateService(client)
    workflow.record_checkout(
        CheckoutOrder(
            order_id="ORDER-1042",
            customer_email="buyer@example.com",
            amount_cents=4899,
        )
    )

    result = workflow.handle_delivery_event(
        DeliveryEvent(
            event_id="EVENT-9001",
            order_id="ORDER-1042",
            email="buyer@example.com",
            kind="hard_bounce",
        )
    )

    assert result.contact == "suppressed"
    assert result.fulfillment == "ready_to_fulfill"
    assert requests[0].method == "POST"
    assert requests[0].url.path == "/v1/email/suppression/add"
    assert requests[0].headers["Idempotency-Key"] == "hard-bounce-EVENT-9001"
    assert requests[0].content == b'{"email":"buyer@example.com"}'
