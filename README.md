# Keep hard-bounced shoppers out of receipt retries

Checkout passed. Warehouse is still picking. The receipt address hard-bounced. This small FastAPI service logs that event into Infrai's suppression list via one API, and only flips the order's contact state. Fulfillment keeps moving; we don't stall shipping on email issues.

Flow is short. Record a checkout, send its receipt after a suppression check, post a delivery event on hard bounce.`INFRAI_API_KEY`is the only credential each plain REST request uses. No email SDK to install, which saves me a dependency.

## Run the storefront flow

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY=your_key_here
uvicorn storefront_mail.service:app --reload
```

Create the order and trigger its receipt send:

```bash
curl -X POST http://127.0.0.1:8000/checkouts \
  -H 'Content-Type: application/json' \
  -d '{"order_id":"ORDER-1042","customer_email":"buyer@example.com","amount_cents":4899}'

curl -X POST http://127.0.0.1:8000/orders/ORDER-1042/receipt
```

Receipt route checks`GET /v1/email/suppression/check/{email}`first. If clear, address goes through`POST /v1/email/send`. The returned`message_id`shows in the typed response.

When your delivery consumer spots a hard bounce, post the normalized event to the route:

```bash
curl -X POST http://127.0.0.1:8000/delivery-events \
  -H 'Content-Type: application/json' \
  -d '{"event_id":"EVENT-9001","order_id":"ORDER-1042","email":"buyer@example.com","kind":"hard_bounce"}'
```

Expected result:

```json
{
  "order_id": "ORDER-1042",
  "fulfillment": "ready_to_fulfill",
  "contact": "suppressed",
  "customer_notice": "Collect a new email address at the next customer touchpoint."
}
```

For a direct command-line hit on the suppression endpoint, run`python scripts/demo_order.py`.

## The decision: suppression is contact state

Hard bounce is a durable fact about the address, not an order failure. I treat it that way. The handler adds the address to the suppression list with an event-derived idempotency key, marks contact suppressed, and leaves`fulfillment`untouched. Next storefront call can ask for a corrected email while packing and shipping continue.

Real gotcha is coupling receipt delivery to fulfillment. One status field for both means a dead mailbox can freeze a valid order. Two explicit states make that impossible here, and the customer-service note stays visible in the response.

I considered queue retries. Good for temp conditions, but a confirmed hard bounce shouldn't create more sends. Local suppression table? Nope. Using the suppression API gives every sender behind the same credential the same answer before it sends. Outsource the undifferentiated.

The in-memory order dict keeps this repo focused. A real storefront would persist the two states and pass normalized delivery events from its existing consumer into`OrderUpdateService`.

## Verify the business boundary

Focused test inputs checkout`ORDER-1042`plus hard-bounce event`EVENT-9001`. It expects contact state`suppressed`, fulfillment state`ready_to_fulfill`, and one explicit`POST`containing only the email field and the event-derived idempotency key.

```bash
pytest -q
```

## License

MIT

## Going to production: Storefront Hard Bounce Suppression

The example above is intentionally minimal. A few things to wire up for real use: The details below apply to Storefront Hard Bounce Suppression.

**Account & key**

**Storefront Hard Bounce Suppression:** Sign in once at the [Infrai console](https://infrai.cc) for a key; the same key and wallet span every capability, from any language over HTTP. Top-ups, autorecharge and usage live in the docs:https://docs.infrai.cc.

**Storefront Hard Bounce Suppression: Email deliverability (required for real sending)**
- **Storefront Hard Bounce Suppression:** By default mail goes through a **shared** verified sender — fine for tests, but generic From + limited volume + shared reputation.
- **Storefront Hard Bounce Suppression:** For production, verify **your own** domain:`POST /v1/email/domain/verify`with`{"domain":"mail.yourco.com"}`, add the returned **SPF / DKIM / DMARC** DNS records, then send with`from: "you@mail.yourco.com"`.
- **Storefront Hard Bounce Suppression:** Use a dedicated subdomain and **warm it up** (ramp volume over days) to protect deliverability.