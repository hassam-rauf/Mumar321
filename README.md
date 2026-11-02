# WooCommerce AI Support Agent — Voiceflow + Make + Vapi

A voice/chat support agent for a WooCommerce store. Voiceflow runs the chat conversation, one Make
scenario does the backend work against the WooCommerce REST API, and a **Vapi phone agent** answers
calls using the same backend ([setup](docs/vapi-setup.md)).

**What it does**

| Feature | Woo API | Notes |
|---|---|---|
| Order tracking | `GET /orders/{id}`, `GET /orders/{id}/notes` | Verifies the billing email before answering; returns status, date, items, tracking |
| Take an order | `POST /orders` (status `pending`) | Collects name, email, phone, product, option, quantity; checks stock first |
| Inventory check | `GET /products?search=`, `GET /products/{id}/variations` | Per-variation stock for variable products |
| Business-hours routing | – | Store-timezone hours from config → call forward (open) or callback message (closed) |

**Demo video:** [demo/woo-ai-support-agent-demo.mp4](demo/woo-ai-support-agent-demo.mp4) (1:47).
It shows the browser test client calling the reference webhook against the local mock store. Every request,
response and Woo API call is visible on screen.

Run the same demo yourself:

```bash
export WOO_URL=http://localhost:8099 WOO_CONSUMER_KEY=ck_demo WOO_CONSUMER_SECRET=cs_demo DEMO_MODE=1 STORE_TZ=America/Denver
python3 scripts/mock_woo.py & python3 scripts/webhook_server.py &
# open http://localhost:8787  — or record it: node demo/record_demo.js http://localhost:8787 27
```

## Architecture

```
 Customer ──► Voiceflow agent ──(API step, POST JSON)──► Make webhook
 (phone/chat)   intents, slots,                           router by "action"
                call forward    ◄──── {ok, message, data, route} ────┘ │
                                                                       ▼
                                                    WooCommerce REST API v3 (/wp-json/wc/v3)
```

Webhook contract (all actions):

```json
// request
{ "action": "track_order | check_stock | create_order | business_hours | callback_request", "payload": { } }
// response
{ "ok": true, "message": "text for the bot to say", "data": { }, "route": "transfer | message | null" }
```

## Repo

```
docker-compose.yml        local WordPress + WooCommerce + MariaDB (+ WP-CLI)
seed/catalog.json         10 products (some out of stock, 1 variable) + 5 orders
seed/seed.php             WP-CLI seeder + REST API key
scripts/setup-store.sh    one-time store setup
scripts/test_api.py       checks every Woo request the scenario uses
scripts/webhook_server.py reference implementation of the Make scenario (same contract)
scripts/test_webhook.py   runs every conversation case against Make or the reference server
scripts/mock_woo.py       offline Woo API mock (no Docker needed)
demo/chat.html            browser test client + live request/response panel (DEMO_MODE=1)
demo/record_demo.js       Playwright script that records the demo video
make/blueprint.json       importable Make scenario (needs manual review — see make/README.md)
docs/make-scenario.md     step-by-step Make build guide
docs/voiceflow-setup.md   intents, slots, API step, call-forward branch
docs/demo-script.md       2–3 min Loom script
vapi/assistant.json       Vapi phone agent: prompt, function tools, transcriber
scripts/vapi_adapter.py   /vapi endpoint: Vapi tool calls -> webhook contract
scripts/vapi_setup.py     creates/updates the Vapi assistant via the Vapi API
scripts/test_vapi.py      simulated Vapi tool calls against /vapi
docs/vapi-setup.md        Vapi setup, test calls and demo recording
```

Python scripts use only the standard library (Python 3.9+).

## Run it

```bash
cp .env.example .env                 # set passwords
docker compose up -d
./scripts/setup-store.sh             # installs WooCommerce, seeds data, prints API key
# paste WOO_CONSUMER_KEY / WOO_CONSUMER_SECRET into .env
python3 scripts/test_api.py --write  # verify every Woo endpoint
```

Make runs in the cloud, so expose the store over HTTPS:

```bash
cloudflared tunnel --url http://localhost:8080      # or: ngrok http 8080
```

Then build the Make scenario ([guide](docs/make-scenario.md)), point Voiceflow's API steps at the
webhook ([guide](docs/voiceflow-setup.md)), and check everything:

```bash
python3 scripts/test_webhook.py https://hook.make.com/xxxx --write
```

**No Docker?** Run against the mock:

```bash
WOO_URL=http://localhost:8099 WOO_CONSUMER_KEY=ck_demo WOO_CONSUMER_SECRET=cs_demo python3 scripts/mock_woo.py &
WOO_URL=http://localhost:8099 WOO_CONSUMER_KEY=ck_demo WOO_CONSUMER_SECRET=cs_demo python3 scripts/webhook_server.py &
WOO_URL=http://localhost:8099 WOO_CONSUMER_KEY=ck_demo WOO_CONSUMER_SECRET=cs_demo python3 scripts/test_webhook.py http://localhost:8787 --write
```

## Business hours

Set in Make's config module (and `.env` for the reference server):
`STORE_TZ`, `BUSINESS_DAYS` (ISO 1=Mon…7=Sun), `BUSINESS_OPEN` / `BUSINESS_CLOSE` (`HHmm`).
`FORCE_ROUTE=transfer|message` overrides the clock, for demos only.

## Things that usually break after moving to WooCommerce

- Wrong base URL — must be `https://store.com/wp-json/wc/v3/...`; REST needs pretty permalinks.
- Basic auth over plain HTTP — Woo rejects it. Use HTTPS (or OAuth 1.0a signatures).
- Read-only API key used for `POST /orders` → 401.
- Order numbers typed as `#1234` not cleaned before the lookup.
- Variable products: stock lives on each variation, not on the parent.
- Business hours checked in the server's timezone (UTC) instead of the store's.

## Security

- API keys only in `.env` (git-ignored) and in Make's key store, never in URLs or Voiceflow.
- Order lookups require the matching billing email, with one generic error for "not found" and
  "wrong email".
- Orders are created as `pending` (unpaid), never paid/processing.

## Screenshots

- `docs/img/voiceflow-canvas.png` — Voiceflow flow *(placeholder)*
- `docs/img/make-scenario.png` — Make scenario *(placeholder)*
- `docs/img/woo-order.png` — created pending order *(placeholder)*
