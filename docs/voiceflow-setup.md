# Voiceflow setup

Voiceflow handles the conversation. Every store lookup is one **API step** that POSTs to the
Make webhook and reads back `ok`, `message`, `route`. The bot never talks to WooCommerce directly.

Step names below are from the Voiceflow workflow canvas; menus get renamed from time to time, so
look for the closest equivalent. For a phone agent use a **Phone** project (needed for Call forward).

## 1. Variables

Create these (Variables tab):

| Variable        | Purpose                                  |
|-----------------|------------------------------------------|
| `webhook_url`   | Make webhook URL (set once in a start Set step) |
| `order_number`  | slot                                     |
| `email`         | slot                                     |
| `product_name`  | slot                                     |
| `option`        | slot (size / variant), optional          |
| `quantity`      | slot                                     |
| `customer_name` | slot                                     |
| `phone`         | slot                                     |
| `reason`        | slot (callback reason)                   |
| `api_ok`, `api_message`, `api_route` | filled from every API response |

## 2. Entities (slots)

| Entity          | Type                              | Example values |
|-----------------|-----------------------------------|----------------|
| `order_number`  | Number (or custom, regex `#?\d+`) | 1234, #1234 |
| `email`         | built-in Email                    | |
| `product_name`  | Custom — list your product names + synonyms | coffee mug, mug; hoodie, zip hoodie; trucker cap, cap |
| `option`        | Custom                            | S, M, L, XL, small, medium, large |
| `quantity`      | Number                            | |
| `customer_name` | built-in Name / Full name         | |
| `phone`         | built-in Phone number             | |

## 3. Intents

| Intent          | Required slots                         | Sample utterances |
|-----------------|----------------------------------------|-------------------|
| `track_order`   | `order_number`, `email`                | where is my order · track order {order_number} · order status |
| `check_stock`   | `product_name` (`option` optional)     | is the {product_name} in stock · do you have {product_name} in {option} |
| `place_order`   | `product_name`, `quantity`, `customer_name`, `email`, `phone` (`option` optional) | I want to order {quantity} {product_name} · buy a {product_name} |
| `talk_to_human` | –                                      | talk to a person · call support · agent please · representative |

For each required slot, add a re-prompt, e.g. *"What's your order number?"*, *"And the email you used at checkout?"*

## 4. API step (same pattern for every action)

| Field        | Value |
|--------------|-------|
| Method       | `POST` |
| URL          | `{webhook_url}` |
| Headers      | `Content-Type: application/json` |
| Body (Raw)   | see per-action bodies below |
| Capture response | `response.ok` → `api_ok` · `response.message` → `api_message` · `response.route` → `api_route` |

Bodies:

```json
{"action": "track_order",  "payload": {"order_number": "{order_number}", "email": "{email}"}}
{"action": "check_stock",  "payload": {"product_name": "{product_name}", "option": "{option}"}}
{"action": "create_order", "payload": {"name": "{customer_name}", "email": "{email}", "phone": "{phone}",
                                       "product_name": "{product_name}", "option": "{option}", "quantity": "{quantity}"}}
{"action": "business_hours", "payload": {}}
{"action": "callback_request", "payload": {"name": "{customer_name}", "phone": "{phone}", "reason": "{reason}"}}
```

After the API step:
- **Success path** → *Message*: `{api_message}`
- **Failure path** (timeout / Make down) → *Message*: "Sorry, I'm having trouble reaching our store right now. Please try again shortly."

The bot just reads `api_message` aloud. All wording lives in Make, so fixes don't need a
Voiceflow republish.

## 5. Flows

**Track order:** `track_order` intent → capture `order_number`, `email` → API (track_order) →
speak `{api_message}` → *"Anything else?"*
If `api_ok` is `false`, offer one retry: *"Want to try a different order number or email?"*

**Check stock:** `check_stock` → capture `product_name` → API (check_stock) → speak `{api_message}`.
If the reply asks *"Which option do you want?"*, capture `option` and call the API again.
If in stock, offer: *"Would you like to place an order?"* → jump to Place order.

**Place order:** `place_order` → capture product, option (if variable), quantity, name, email,
phone → confirm: *"So that's {quantity} x {product_name} for {customer_name}, correct?"* →
on yes, API (create_order) → speak `{api_message}`.

**Talk to a human / call forwarding:**
`talk_to_human` → API (business_hours) → **Condition** on `api_route`:
- `api_route == "transfer"` → speak `{api_message}` → **Call forward** step (phone: the store's
  support number / SIP). For a chat project use your live-agent handoff instead.
- else (`"message"`) → speak `{api_message}` → capture `customer_name`, `phone`, `reason` →
  API (callback_request) → speak `{api_message}` → end.

Also use the business-hours check as the global **No match** fallback after two misses, so a stuck
caller always reaches a human or leaves a callback.

## 6. Agent / LLM mode (optional)

If you use Voiceflow's agent with tools instead of a fixed canvas, create one **API tool** per
action with the same URL and body, and describe each one, e.g.
*"track_order — look up an order. Requires order_number and the email used at checkout. Always
say the returned message to the user verbatim."* Keep the business-hours → call forward branch as
a workflow so transfers stay deterministic.

## 7. Test before Make is ready

Run the local reference server and expose it:

```bash
python3 scripts/webhook_server.py            # http://localhost:8787
cloudflared tunnel --url http://localhost:8787
```

Set `webhook_url` to the tunnel URL. When Make is built, swap the URL — nothing else changes.
