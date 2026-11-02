# Vapi voice agent setup

The same store backend, now answering **phone calls**. Vapi handles speech-to-text, the LLM and
text-to-speech; every store action is a Vapi *function tool* that calls `webhook_server.py` at
`/vapi`. The adapter (`scripts/vapi_adapter.py`) turns Vapi's tool calls into the normal webhook
contract, so Voiceflow, Make and Vapi all share one backend and one set of tests.

```
 Caller ──► Vapi (Deepgram STT → GPT-4o-mini → TTS)
              │ tool call: track_order / check_stock / create_order / business_hours / callback_request
              ▼
         POST {PUBLIC_URL}/vapi  ──►  webhook_server.py  ──►  WooCommerce REST API
              ◄── {"results": [{"toolCallId", "result": "text for the agent to say"}]}
```

## 1. Run the backend (mock store is fine for a demo)

```bash
export WOO_URL=http://localhost:8099 WOO_CONSUMER_KEY=ck_demo WOO_CONSUMER_SECRET=cs_demo
python3 scripts/mock_woo.py &
python3 scripts/webhook_server.py &
cloudflared tunnel --url http://localhost:8787      # or: ngrok http 8787
```

Copy the `https://…trycloudflare.com` URL.

## 2. Configure `.env`

```
PUBLIC_URL=https://xyz.trycloudflare.com   # the tunnel URL from step 1
VAPI_API_KEY=...                           # Vapi dashboard -> API Keys -> private key
VAPI_SECRET=pick-a-long-random-string      # optional; Vapi sends it as x-vapi-secret
TRANSFER_NUMBER=+15551234567               # optional; real number for "talk to a person"
```

Restart `webhook_server.py` after setting `VAPI_SECRET` so it starts checking the header.

## 3. Create the assistant

```bash
python3 scripts/vapi_setup.py --dry-run   # check the payload
python3 scripts/vapi_setup.py             # creates "Woo Store Voice Agent"
```

Add the printed `VAPI_ASSISTANT_ID` to `.env`; running the script again then updates the same
assistant. If Vapi rejects a field (their schema changes from time to time), the error names it:
remove or rename it in `vapi/assistant.json` and run again. Pick a voice in the dashboard.

## 4. Test

```bash
python3 scripts/test_vapi.py http://localhost:8787     # simulated Vapi tool calls, no phone needed
```

Then in the Vapi dashboard open the assistant and click **Talk to Assistant** for a browser call,
or attach a phone number to it. Try:

| Say | Expected |
|-----|----------|
| "Where is my order 27? Email sara.lee@example.com" | status, items and UPS tracking |
| "Do you have the hoodie?" → "Large" | lists S and L, then price and stock for L |
| "I want two coffee mugs" | collects name, email, phone, reads back, creates a pending order |
| "Can I talk to a person?" | transfer during hours, otherwise takes a callback |

Each finished call is logged to `data/calls.jsonl` (summary, transcript, recording URL).

## Recording the demo

Record your screen with the Vapi browser call on one side and the `webhook_server.py` terminal on
the other, so viewers hear the agent and see each tool call hit the store. 90 seconds is enough:
order tracking, a stock check with a size, and a callback request.
