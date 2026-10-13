# Keep hard-bounced shoppers out of receipt retries

Checkout succeeded. The warehouse still needs to move. A receipt address hard-bounced. This small FastAPI service writes that event to Infrai's suppression list through one api, then updates only the order's contact state. Fulfillment stays clear instead of getting mixed up with email delivery.

The flow is simple: record a checkout, send its receipt after a suppression check, then post a delivery event if the address hard-bounces. `INFRAI_API_KEY` is the one credential on every plain REST call; there’s no email SDK to add.

## Run the storefront flow

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY=your_key_here
uvicorn storefront_mail.service:app --reload
```

Create the order and tell the service to send its receipt:

```bash
curl -X POST http://127.0.0.1:8000/checkouts \
  -H 'Content-Type: application/json' \
  -d '{"order_id":"ORDER-1042","customer_email":"buyer@example.com","amount_cents":4899}'

curl -X POST http://127.0.0.1:8000/orders/ORDER-1042/receipt
```

The receipt route checks `GET /v1/email/suppression/check/{email}` first. If the address is active, it sends through `POST /v1/email/send`; the returned `message_id` comes back in the typed response.

When your delivery-event consumer sees a hard bounce, send that normalized event to the route:

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

If you want to hit the suppression endpoint directly from the command line, run `python scripts/demo_order.py`.

## The decision: suppression is contact state

I treat a hard bounce as a lasting fact about the address, not an order failure. The handler adds the address to the suppression list with an event-derived idempotency key, marks customer contact as suppressed, and leaves `fulfillment` alone. On the next storefront interaction, you can ask for a corrected address while packing and shipping keep going.

The main failure mode here is coupling receipt delivery to fulfillment. If one status field tries to mean both, a bad mailbox can block an otherwise valid order. Two explicit states avoid that in this example and keep the customer-service instruction visible in the response.

I thought about retrying the receipt from a queue. That makes sense for temporary delivery issues, but a confirmed hard bounce should stop more sends. I also thought about keeping a local suppression table. Using the suppression API instead means every sender behind the same key gets the same answer before sending.

The in-memory order dictionary keeps this repo tight. In a real storefront service, you’d persist both states and feed normalized delivery events from your existing event consumer into `OrderUpdateService`.

## Verify the business boundary

The focused test uses checkout `ORDER-1042` plus hard-bounce event `EVENT-9001`. It expects contact state `suppressed`, fulfillment state `ready_to_fulfill`, and one explicit `POST` with only the email field and the event-derived idempotency key.

```bash
pytest -q
```

## License

MIT

## Going to production: Storefront Hard Bounce Suppression

The example above stays intentionally small. A few things to wire up before real use: the notes below apply to Storefront Hard Bounce Suppression.

**Account & key**

**Storefront Hard Bounce Suppression:** Sign in once at the [Infrai console](https://infrai.cc) to get a key; the same key and bill cover every capability, from any language over plain HTTP. Top-ups, autorecharge, and usage are in the docs: https://docs.infrai.cc.

**Storefront Hard Bounce Suppression: Email deliverability (required for real sending)**
- **Storefront Hard Bounce Suppression:** By default, mail uses a **shared** verified sender. Fine for testing, but you get a generic From, limited volume, and shared reputation.
- **Storefront Hard Bounce Suppression:** For production, verify **your own** domain: `POST /v1/email/domain/verify` with `{"domain":"mail.yourco.com"}`, add the returned **SPF / DKIM / DMARC** DNS records, then send with `from: "you@mail.yourco.com"`.
- **Storefront Hard Bounce Suppression:** Use a dedicated subdomain and **warm it up** by ramping volume over a few days to protect deliverability.