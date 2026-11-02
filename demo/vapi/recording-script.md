# Live voice call: recording script (about 90 seconds)

Two ways to record a real, unscripted call with the same agent (same prompt and tools from
`vapi/assistant.json`, same backend):

- **Gemini Live web call (free):** `http://localhost:8787/gemini`, no tunnel, no credits.
- **Vapi (paid credits):** Vapi dashboard -> Talk to Assistant, needs the tunnel (see the end).

## Before you press record (Gemini Live)

- Running, each in its own terminal: `python scripts/mock_woo.py` and
  `python -u scripts/webhook_server.py` (`.env` has `DEMO_MODE=1`, `FORCE_ROUTE=message`
  and `GEMINI_API_KEY`).
- Open `http://localhost:8787/gemini` in **Chrome or Edge**, allow the microphone.
  Browser window about 1280x720 or larger, zoom 100%.
- Screen layout, 1920x1080: browser on the left two thirds, the `webhook_server.py` terminal on
  the right third, font size 16+, cleared (`cls`) before recording.
- Recorder: OBS or Windows Game Bar (Win+Alt+R). **Capture system audio and the microphone**, so
  both voices are in the video. **Use headphones**, or the agent hears itself and interrupts.
- Speak slowly and clearly. Pause after each sentence; the agent answers when you stop talking.

## The call

| Time | You say | Agent should do | Panels / terminal show |
|---|---|---|---|
| 0:00 | (click **Start call**) | Greets: track, stock, order, or connect to team | timer starts |
| 0:08 | "Hi, where is my order twenty-seven?" | Asks for the checkout email | – |
| 0:13 | "sara dot lee at example dot com" | Completed and shipped, Logo T-Shirt, UPS tracking | `track_order` · `GET /orders/27 → 200` |
| 0:28 | "Do you have the zip hoodie?" | "In stock in S and L, which size?" | `check_stock` · product search |
| 0:35 | "Large, please" | 2 left, $49 each | `check_stock {"option": "L"}` · variations |
| 0:45 | "Is the trucker cap in stock?" | Out of stock | `check_stock` |
| 0:52 | "Can I talk to a real person?" | Closed now, asks name, phone, reason | `business_hours` |
| 1:00 | "Jane Doe, plus one five five five, zero one one zero, about a bulk order" | Confirms the callback | `callback_request` |
| 1:15 | "That's all, thanks, bye" | Says goodbye and hangs up by itself | `end_call` · "Call ended" |

Optional: "I want to order two coffee mugs" -> it collects name, email and phone, reads them
back, and creates a pending order (`create_order` · `POST /orders → 201`).

If something goes wrong, click **End call**, `cls` the terminal and start again: every call is a
fresh session.

## After recording

- Trim the start and end, add a title card: "AI voice agent for WooCommerce: live calls, real store API".
- Add captions (CapCut auto-captions are enough): most people watch LinkedIn muted.
- Wording that stays accurate: "Live call on Gemini Live; the same agent config deploys to Vapi
  for phone numbers." Do not call this recording a Vapi call.
- Upwork portfolio: only the demo names, numbers and emails above on screen.

## Vapi version (when the Vapi wallet has credits)

1. `cloudflared tunnel --url http://localhost:8787` and put the new `https://…trycloudflare.com`
   URL in `.env` as `PUBLIC_URL` (it changes every time the tunnel restarts).
2. `python scripts/vapi_setup.py` (updates the assistant in `VAPI_ASSISTANT_ID`).
3. Vapi dashboard -> Assistants -> "Woo Store Voice Agent" -> **Talk to Assistant**, same call as above.
