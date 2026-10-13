from __future__ import annotations

import json

from storefront_mail.infrai_client import InfraiEmailClient
from storefront_mail.order_updates import CheckoutOrder, DeliveryEvent, OrderUpdateService


def main() -> None:
    workflow = OrderUpdateService(InfraiEmailClient())
    workflow.record_checkout(
        CheckoutOrder(
            order_id="ORDER-1042",
            customer_email="chenhua@changba.com",
            amount_cents=4899,
        )
    )
    result = workflow.handle_delivery_event(
        DeliveryEvent(
            event_id="EVENT-9001",
            order_id="ORDER-1042",
            email="chenhua@changba.com",
            kind="hard_bounce",
        )
    )
    print(json.dumps(result.model_dump(mode="json"), indent=2))


if __name__ == "__main__":
    main()
