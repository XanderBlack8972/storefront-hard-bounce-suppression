from __future__ import annotations

from fastapi import FastAPI, HTTPException

from .infrai_client import InfraiEmailClient, InfraiError
from .order_updates import (
    CheckoutOrder,
    DeliveryEvent,
    OrderUpdate,
    OrderUpdateService,
    ReceiptResult,
)


def create_app(email_client: InfraiEmailClient | None = None) -> FastAPI:
    app = FastAPI(title="Storefront bounce suppression")
    workflow = OrderUpdateService(email_client or InfraiEmailClient())

    @app.post("/checkouts", response_model=CheckoutOrder, status_code=201)
    def checkout(order: CheckoutOrder) -> CheckoutOrder:
        return workflow.record_checkout(order)

    @app.post("/orders/{order_id}/receipt", response_model=ReceiptResult)
    def receipt(order_id: str) -> ReceiptResult:
        try:
            return workflow.send_receipt(order_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="order not found") from None
        except InfraiError as exc:
            status = exc.status_code if 400 <= exc.status_code < 500 else 502
            raise HTTPException(status_code=status, detail=exc.detail) from exc

    @app.post("/delivery-events", response_model=OrderUpdate)
    def delivery_event(event: DeliveryEvent) -> OrderUpdate:
        try:
            return workflow.handle_delivery_event(event)
        except KeyError:
            raise HTTPException(status_code=404, detail="order not found") from None
        except InfraiError as exc:
            status = exc.status_code if 400 <= exc.status_code < 500 else 502
            raise HTTPException(status_code=status, detail=exc.detail) from exc

    return app


app = create_app()
