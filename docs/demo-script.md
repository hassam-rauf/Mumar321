# Loom demo script (2–3 min)

**Setup before recording**
- Store running, Make scenario ON, Voiceflow prototype open (voice or chat).
- Two tabs ready: Make scenario (to show runs live) and Woo admin → Orders.
- Know one seeded order number for `sara.lee@example.com` (printed by `setup-store.sh`, or run
  `python3 scripts/test_api.py`). Below it's `#1234`.

---

**0:00 – 0:15 · Intro (camera on)**
> "Hi, I'm ___. You said your Voiceflow + Make bot broke after moving to WooCommerce. I rebuilt
> that exact stack on a test Woo store — order tracking, taking orders, stock checks and
> business-hours call forwarding. Here it is working."

Show the architecture diagram from the README for 3 seconds.

**0:15 – 0:45 · Order tracking (happy path)**
- You: "Where's my order?" → bot asks number → "1234" → bot asks email → "sara.lee@example.com"
- Bot: *"Order #1234 is completed and shipped… Tracking: UPS 1Z999AA10123456784."*
- Flip to Make: point at the run → webhook → router → HTTP GET order → response.

**0:45 – 1:00 · Error case: wrong email**
- Same order number, email "someone@else.com".
- Bot: *"I couldn't find an order with that number and email…"*
> "Same message for wrong number and wrong email, so nobody can look up other people's orders."

**1:00 – 1:30 · Inventory check**
- "Do you have the trucker cap?" → *out of stock*.
- "Is the hoodie in stock?" → *"in stock in: S, L. Which option?"* → "Medium" → *out of stock*.
> "Variable products are checked per variation — a common bug after migrations is reading the
> parent's stock."

**1:30 – 2:00 · Taking an order**
- "I want to order 1 large hoodie" → name, email, phone → confirm → *"Done! Order #… created…"*
- Flip to Woo admin → Orders: the new **Pending payment** order is there.

**2:00 – 2:40 · Business hours / call forwarding**
- In Make config set `force_route` = `transfer` → "Can I talk to someone?" → *"Our team is
  available now…"* → Call forward step fires (show the step / ringing).
- Set `force_route` = `message` → ask again → *"We're closed right now… leave your name…"* →
  give name, phone, reason → *"Thanks Jane! We'll call you…"* → show the Google Sheet row.
> "Hours and timezone are config values in one module, and the time is calculated in the
> store's timezone, not the server's."
- Clear `force_route` afterwards.

**2:40 – 3:00 · Close**
> "For your bot I'd check the same points on your two sites: the Woo API base URL and keys,
> HTTPS auth, variable-product stock, and the timezone logic, then test every path end to end.
> Happy to start right away."
