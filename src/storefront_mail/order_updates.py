from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field

from .infrai_client import InfraiEmailClient


EmailAddress = Annotated[str, Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")]


class FulfillmentState(StrEnum):
    READY = "ready_to_fulfill"
    SHIPPED = "shipped"


class ContactState(StrEnum):
    ACTIVE = "active"
    SUPPRESSED = "suppressed"


class CheckoutOrder(BaseModel):
    order_id: str = Field(min_length=1)
    customer_email: EmailAddress
    amount_cents: int = Field(ge=0)
    fulfillment: FulfillmentState = FulfillmentState.READY
    contact: ContactState = ContactState.ACTIVE


class DeliveryEvent(BaseModel):
    event_id: str = Field(min_length=1)
    order_id: str = Field(min_length=1)
    email: EmailAddress
    kind: str


class OrderUpdate(BaseModel):
    order_id: str
    fulfillment: FulfillmentState
    contact: ContactState
    customer_notice: str


class ReceiptResult(BaseModel):
    order_id: str
    status: str
    message_id: str | None = None


class OrderUpdateService:
    def __init__(self, email_client: InfraiEmailClient) -> None:
        self._email_client = email_client
        self._orders: dict[str, CheckoutOrder] = {}

    def record_checkout(self, order: CheckoutOrder) -> CheckoutOrder:
        self._orders[order.order_id] = order
        return order

    def send_receipt(self, order_id: str) -> ReceiptResult:
        order = self._get_order(order_id)
        suppression = self._email_client.suppression_check(str(order.customer_email))
        if bool(suppression.get("suppressed")):
            order.contact = ContactState.SUPPRESSED
            return ReceiptResult(order_id=order_id, status="suppressed")

        dollars = f"{order.amount_cents / 100:.2f}"
        sent = self._email_client.send_receipt(
            to=str(order.customer_email),
            subject=f"Receipt for order {order.order_id}",
            body=f"Thanks for your order. Your total was ${dollars}.",
            idempotency_key=f"receipt-{order.order_id}",
        )
        return ReceiptResult(
            order_id=order_id,
            status="sent",
            message_id=str(sent["message_id"]),
        )

    def handle_delivery_event(self, event: DeliveryEvent) -> OrderUpdate:
        order = self._get_order(event.order_id)
        if event.kind == "hard_bounce":
            self._email_client.suppression_add(
                str(event.email),
                idempotency_key=f"hard-bounce-{event.event_id}",
            )
            order.contact = ContactState.SUPPRESSED
            notice = "Collect a new email address at the next customer touchpoint."
        else:
            notice = "No contact change required."

        return OrderUpdate(
            order_id=order.order_id,
            fulfillment=order.fulfillment,
            contact=order.contact,
            customer_notice=notice,
        )

    def _get_order(self, order_id: str) -> CheckoutOrder:
        order = self._orders.get(order_id)
        if order is None:
            raise KeyError(order_id)
        return order
