# Make scenario: build guide

One scenario, one webhook, a router by `action`. Every branch ends in a **Webhooks → Webhook response**.
Module numbers below (1, 2, 10, 11 …) are the IDs used in the formulas — your IDs will differ, so
re-map the pills when you build it.

`scripts/webhook_server.py` implements exactly the same logic in Python. If Make output looks
wrong, compare it with that server's output for the same request.

```
1 Webhook ─ 2 Set config ─ 3 Router ─┬─ track_order ─── 10 GET order ── 11 Router ─┬─ 12 GET notes ─ 13 Respond (ok)
                                     │                                             └─ 15 Respond (not found / wrong email)
                                     ├─ check_stock ─── 20 GET search ─ 21 Router ─┬─ 22 Respond (not found)
                                     │                                             └─ 23 GET variations ─ 24 Set vars ─ 25 Router ─ 26/27 Respond
                                     ├─ create_order ── 30 GET search ─ 31 Router ─┬─ 32 Respond (not found)
                                     │                                             └─ 33 GET variations ─ 34 Set vars ─ 35 Router ─┬─ 36 POST order ─ 37 Respond
                                     │                                                                                            └─ 38 Respond (unavailable)
                                     ├─ business_hours  40 Set vars ── 41 Router ─┬─ 42 Respond (transfer)
                                     │                                             └─ 43 Respond (message)
                                     ├─ callback_request 50 Google Sheets: Add row ─ 51 Respond
                                     └─ (fallback) ─── 60 Respond (unknown action)
```

## 0. Before you start

- The Woo store must be reachable from the internet over **HTTPS**. For the local Docker store:
  `cloudflared tunnel --url http://localhost:8080` (or `ngrok http 8080`) and use that URL.
  The compose file already makes WordPress follow the tunnel host.
- Make → **Keys** (or Connections) → add a **Basic auth** key: username = `ck_...`, password = `cs_...`.
  Never paste keys into module URLs.
- Scenario scheduling: **Immediately** (as data arrives).

## 1. Webhooks → Custom webhook

Name it `woo-support`. Copy the URL into `.env` as `WEBHOOK_URL`.
Click **Re-determine data structure**, then send one sample that contains every field:

```bash
curl -X POST "$WEBHOOK_URL" -H 'Content-Type: application/json' -d '{"action":"track_order","payload":{
 "order_number":"1","email":"a@b.com","product_name":"mug","option":"L","quantity":"1",
 "name":"Jane Roe","phone":"+15550110","reason":"test"}}'
```

## 2. Tools → Set multiple variables (config)

| Variable      | Value (demo)                    |
|---------------|---------------------------------|
| `woo_url`     | `https://YOUR-TUNNEL.trycloudflare.com` (no trailing slash) |
| `tz`          | `America/New_York`              |
| `open_days`   | `1,2,3,4,5` (ISO: 1=Mon … 7=Sun) |
| `open_hhmm`   | `900`                           |
| `close_hhmm`  | `1700`                          |
| `force_route` | empty (set `transfer` or `message` only to demo a branch) |

The client changes hours here; nothing else in the scenario is hard-coded.

## 3. Router — one route per action

Filter on each route: `{{1.action}}` **Text operators: Equal to** `track_order` / `check_stock` /
`create_order` / `business_hours` / `callback_request`. Mark a 6th route as **fallback**.

All HTTP modules below: **HTTP → Make a Basic Auth request**, credential = your key,
**Parse response = Yes**, and under advanced settings **Evaluate all states as errors = No**
(so a 404 reaches our filters instead of stopping the run).

---

## Route A — `track_order`

**10 HTTP GET**
`{{2.woo_url}}/wp-json/wc/v3/orders/{{replace(1.payload.order_number; /\D/g; emptystring)}}`
(the regex strips `#` and spaces, so "#1234" works).

**11 Router**
- Route "match" — filter, both conditions (AND):
  - `{{10.statusCode}}` Numeric: Equal to `200`
  - `{{lower(trim(10.data.billing.email))}}` Text: Equal to `{{lower(trim(1.payload.email))}}`
- Route "no match" — **fallback**.

> Not found and wrong email give the **same** answer on purpose, so nobody can fish order
> details by guessing order numbers.

**12 HTTP GET** `{{2.woo_url}}/wp-json/wc/v3/orders/{{10.data.id}}/notes` — query string `type` = `customer`.

**13 Webhook response** — status `200`, header `Content-Type: application/json`, body:

```json
{
  "ok": true,
  "message": "Order #{{10.data.number}} is {{switch(10.data.status; pending; pending payment; processing; being processed; on-hold; on hold; completed; completed and shipped; 10.data.status)}}. It was placed on {{formatDate(10.data.date_created; MMM D, YYYY)}} and includes {{join(map(10.data.line_items; name); , )}}. Tracking: {{ifempty(first(map(10.data.meta_data; value; key; _tracking_number)); ifempty(first(map(12.data; note)); not available yet))}}.",
  "data": { "order_id": "{{10.data.id}}", "status": "{{10.data.status}}" },
  "route": null
}
```

**15 Webhook response** (fallback):

```json
{"ok": false, "message": "I couldn't find an order with that number and email. Please double-check both.", "data": {}, "route": null}
```

---

## Route B — `check_stock`

**20 HTTP GET** `{{2.woo_url}}/wp-json/wc/v3/products`
query string: `search` = `{{1.payload.product_name}}`, `per_page` = `5`, `status` = `publish`.

**21 Router**
- Route "not found": `{{length(20.data)}}` Numeric: Equal to `0` → **22 Webhook response**:
  `{"ok": false, "message": "I couldn't find a product called {{1.payload.product_name}}. Could you try another name?", "data": {}, "route": null}`
- Fallback → continue.

**23 HTTP GET** `{{2.woo_url}}/wp-json/wc/v3/products/{{20.data[1].id}}/variations`, query `per_page` = `50`.
For simple products this simply returns `[]`, so one linear path handles both types.

**24 Tools → Set multiple variables**

Variation lookup uses the SKU convention `PARENTSKU-OPTION` (demo seed: `HOODIE-L`).
`SKU` below means the text `{{upper(20.data[1].sku)}}-{{upper(1.payload.option)}}`.

| Variable  | Value |
|-----------|-------|
| `is_var`  | `{{if(20.data[1].type = variable; true; false)}}` |
| `status`  | `{{if(20.data[1].type = variable; first(map(23.data; stock_status; sku; SKU)); 20.data[1].stock_status)}}` |
| `qty`     | `{{if(20.data[1].type = variable; first(map(23.data; stock_quantity; sku; SKU)); 20.data[1].stock_quantity)}}` |
| `in_stock_options` | `{{replace(join(map(23.data; sku; stock_status; instock); , ); {{upper(20.data[1].sku)}}-; emptystring)}}` |
| `label`   | `{{20.data[1].name}}{{if(1.payload.option; ({{upper(1.payload.option)}}); emptystring)}}` |

Make can't read a variable inside the same "Set multiple variables" module, so the stock
sentence is built in the response below.

> If the client's variations don't follow the SKU pattern, swap `map(...sku...)` for an
> **Iterator** on `23.data` + filter `lower(attributes[1].option) = lower(1.payload.option)`.

**25 Router**
- Route "ask for option" — AND: `{{24.is_var}}` Boolean: Equal to `true` · `{{1.payload.option}}` Basic: Does not exist
  → **26 Webhook response**:

  ```json
  {"ok": true, "message": "{{20.data[1].name}} is in stock in: {{ifempty(24.in_stock_options; none right now)}}. Which option do you want?", "data": {"product_id": "{{20.data[1].id}}"}, "route": null}
  ```
- Fallback → **27 Webhook response**:

  ```json
  {
    "ok": true,
    "message": "{{24.label}} is {{if(24.status = instock; in stock ({{ifempty(24.qty; available)}} left); out of stock)}} at ${{20.data[1].price}}.",
    "data": { "product_id": "{{20.data[1].id}}", "stock_status": "{{24.status}}", "stock_quantity": "{{24.qty}}" },
    "route": null
  }
  ```

  (If the option doesn't exist, `24.status` is empty and the bot says "out of stock" — fine for a demo.)

---

## Route C — `create_order`

**30 HTTP GET** products search — same as module 20.
**31 Router** — "not found" (`length(30.data) = 0`) → **32 Webhook response**
`{"ok": false, "message": "I couldn't find {{1.payload.product_name}} in our store.", "data": {}, "route": null}`; fallback → continue.
**33 HTTP GET** variations — same as module 23, with `30.data[1].id`.

**34 Set multiple variables** — same `status`, `qty`, `label` as module 24 (pointing to 30/33), plus:

| Variable  | Value |
|-----------|-------|
| `var_id`  | `{{if(30.data[1].type = variable; first(map(33.data; id; sku; SKU)); 0)}}` |
| `want`    | `{{ifempty(parseNumber(1.payload.quantity); 1)}}` |
| `first`   | `{{first(split(trim(1.payload.name); space))}}` |
| `last`    | `{{trim(replace(trim(1.payload.name); first(split(trim(1.payload.name); space)); emptystring))}}` |

**35 Router**
- Route "available" — AND:
  - `{{34.status}}` Text: Equal to `instock`
  - `{{ifempty(34.qty; 99999)}}` Numeric: Greater than or equal to `{{34.want}}`
- Fallback "unavailable" → **38 Webhook response**:
  `{"ok": false, "message": "Sorry, {{34.label}} {{if(34.status = instock; only has {{34.qty}} left. Want that many instead?; is not available right now.)}}", "data": {}, "route": null}`

**36 HTTP POST** `{{2.woo_url}}/wp-json/wc/v3/orders` — Body type **Raw**, content type **JSON**:

```json
{
  "status": "pending",
  "set_paid": false,
  "billing": {
    "first_name": "{{34.first}}", "last_name": "{{34.last}}",
    "email": "{{trim(1.payload.email)}}", "phone": "{{trim(1.payload.phone)}}"
  },
  "line_items": [ { "product_id": {{30.data[1].id}}, "variation_id": {{34.var_id}}, "quantity": {{34.want}} } ],
  "customer_note": "Created by the AI support agent."
}
```

Status `pending` = an unpaid order the shop can follow up on. It does not reduce stock.
The API key needs **Read/Write** permission for this call.

**37 Webhook response**:

```json
{
  "ok": {{if(36.statusCode = 201; true; false)}},
  "message": "{{if(36.statusCode = 201; Done! Order #{{36.data.number}} for {{34.want}} x {{34.label}} (total ${{36.data.total}}) is created. We've saved it as pending and will email the payment link to {{1.payload.email}}.; Sorry, I couldn't create the order. A team member will follow up.)}}",
  "data": { "order_id": "{{36.data.id}}", "payment_url": "{{36.data.payment_url}}" },
  "route": null
}
```

---

## Route D — `business_hours`

**40 Set multiple variables**

| Variable | Value |
|----------|-------|
| `dow`    | `{{formatDate(now; E; 2.tz)}}` (ISO weekday 1–7 in the **store** timezone) |
| `hhmm`   | `{{parseNumber(formatDate(now; HHmm; 2.tz))}}` (e.g. 14:05 → `1405`) |

**41 Router**
- Route "transfer" — filter with two OR groups:
  - Group 1: `{{2.force_route}}` Text: Equal to `transfer`
  - **OR** Group 2 (AND): `{{2.force_route}}` Basic: Does not exist ·
    `{{2.open_days}}` Text: Contains `{{40.dow}}` ·
    `{{40.hhmm}}` Numeric ≥ `{{2.open_hhmm}}` ·
    `{{40.hhmm}}` Numeric < `{{2.close_hhmm}}`
  → **42 Webhook response**:
  `{"ok": true, "message": "Our team is available now. Connecting you to a human agent.", "data": {"open": true}, "route": "transfer"}`
- Fallback → **43 Webhook response**:
  `{"ok": true, "message": "We're closed right now. Our hours are Mon-Fri 9:00-17:00 ({{2.tz}}). Leave your name, phone number and the reason for your call, and we'll call you back.", "data": {"open": false}, "route": "message"}`

Because the time is computed in `2.tz`, it is correct no matter where Make's servers run, and
daylight-saving changes are handled by the timezone database.

## Route E — `callback_request`

**50 Google Sheets → Add a row** (sheet columns: Time, Name, Phone, Reason) with
`{{now}}`, `{{1.payload.name}}`, `{{1.payload.phone}}`, `{{1.payload.reason}}`.
(Or **Email → Send an email** to the shop.)
**51 Webhook response**:
`{"ok": true, "message": "Thanks {{first(split(1.payload.name; space))}}! We'll call you at {{1.payload.phone}} during business hours.", "data": {}, "route": null}`

## Fallback route

**60 Webhook response**: `{"ok": false, "message": "Sorry, I can't help with that yet.", "data": {}, "route": null}`

## Error handling

Right-click each HTTP module → **Add error handler** → **Webhook response**:

```json
{"ok": false, "message": "Sorry, our store system isn't responding right now. Please try again in a few minutes.", "data": {}, "route": null}
```

## Notes

- **Quotes in text:** a customer's text containing `"` breaks a raw JSON body. If that matters,
  build the body with **JSON → Create JSON** and pass its output to the Webhook response.
- **Test it:** `python3 scripts/test_webhook.py "$WEBHOOK_URL"` runs every case against Make
  and prints PASS/FAIL. Results should match the local reference server.
- **Common Woo-migration bugs this fixes:** wrong base URL (`/wp-json/wc/v3`), missing pretty
  permalinks (REST returns 404), Basic auth over plain HTTP (Woo rejects it — use HTTPS),
  read-only key on `POST /orders` (401), order number with `#`, variable products reporting
  parent stock instead of variation stock, and business hours computed in UTC instead of the
  store timezone.
