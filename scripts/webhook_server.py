#!/usr/bin/env python3
"""Reference implementation of the Make scenario (same request/response contract).

Use it to (a) test the Voiceflow agent before Make is built, and (b) compare Make's output
against known-good behaviour. Make stays the production backend.

Usage: python3 scripts/webhook_server.py [--port 8787]
Request:  {"action": "...", "payload": {...}}
Response: {"ok": bool, "message": str, "data": {...}, "route": "transfer" | "message" | null}
"""
import json, os, re, sys
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from zoneinfo import ZoneInfo

import gemini_live
import woo as woo_mod
from vapi_adapter import handle_vapi
from woo import Woo, WooError, load_env

load_env()
woo = Woo()
DEMO = os.environ.get("DEMO_MODE") == "1"
DEMO_PAGE = Path(__file__).resolve().parent.parent / "demo" / "chat.html"
VOICE_PAGE = Path(__file__).resolve().parent.parent / "demo" / "voice_call.html"
GEMINI_PAGE = Path(__file__).resolve().parent.parent / "demo" / "gemini_call.html"

STATUS_LABELS = {
    "pending": "pending payment", "processing": "being processed", "on-hold": "on hold",
    "completed": "completed and shipped", "cancelled": "cancelled", "refunded": "refunded",
    "failed": "failed (payment did not go through)",
}
DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def reply(ok, message, data=None, route=None):
    return {"ok": ok, "message": message, "data": data or {}, "route": route}


def money(v):
    return f"${float(v):.2f}"


# ---------------------------------------------------------------- track_order
def track_order(p):
    order_no = re.sub(r"\D", "", str(p.get("order_number", "")))
    email = str(p.get("email", "")).strip().lower()
    if not order_no or not email:
        return reply(False, "Please give me your order number and the email used at checkout.")
    mismatch = reply(False, "I couldn't find an order with that number and email. Please double-check both.")
    try:
        order = woo.get(f"/orders/{order_no}")
    except WooError as e:
        if e.status in (400, 404):
            return mismatch
        raise
    # Same message for "not found" and "wrong email" so order details can't be fished out.
    if order["billing"]["email"].strip().lower() != email:
        return mismatch

    items = ", ".join(f'{i["quantity"]} x {i["name"]}' for i in order["line_items"])
    placed = datetime.fromisoformat(order["date_created"]).strftime("%b %d, %Y")
    meta = {m["key"]: m["value"] for m in order.get("meta_data", [])}
    tracking = None
    if meta.get("_tracking_number"):
        tracking = f'{meta.get("_tracking_provider", "")} {meta["_tracking_number"]}'.strip()
    else:
        for n in woo.get(f"/orders/{order_no}/notes", type="customer"):
            if "tracking" in n["note"].lower():
                tracking = n["note"]
                break

    msg = (f"Order #{order['number']} is {STATUS_LABELS.get(order['status'], order['status'])}. "
           f"It was placed on {placed} and includes {items}.")
    msg += f" Tracking: {tracking}." if tracking else " There is no tracking number yet."
    return reply(True, msg, {"order_id": order["id"], "status": order["status"], "items": items,
                             "tracking": tracking, "total": order["total"]})


# ---------------------------------------------------------------- products
def find_product(name):
    results = woo.get("/products", search=name, per_page=5, status="publish")
    return results[0] if results else None


def option_of(variation):
    return variation["attributes"][0]["option"] if variation.get("attributes") else ""


def stock_text(item):
    if item["stock_status"] != "instock":
        return "out of stock"
    qty = item.get("stock_quantity")
    return f"in stock ({qty} left)" if qty is not None else "in stock"


def check_stock(p):
    name = str(p.get("product_name", "")).strip()
    option = str(p.get("option", "")).strip().lower()
    if not name:
        return reply(False, "Which product would you like me to check?")
    prod = find_product(name)
    if not prod:
        return reply(False, f"I couldn't find a product called \"{name}\". Could you try another name?")

    if prod["type"] == "variable":
        variations = woo.get(f"/products/{prod['id']}/variations", per_page=50)
        if option:
            match = next((v for v in variations if option_of(v).lower() == option), None)
            if not match:
                opts = ", ".join(option_of(v) for v in variations)
                return reply(False, f"{prod['name']} comes in {opts}. Which one do you want?")
            return reply(True, f"{prod['name']} ({option_of(match)}) is {stock_text(match)} at {money(match['price'])}.",
                         {"product_id": prod["id"], "variation_id": match["id"],
                          "stock_status": match["stock_status"], "stock_quantity": match["stock_quantity"]})
        in_stock = ", ".join(option_of(v) for v in variations if v["stock_status"] == "instock")
        return reply(True, f"{prod['name']} is in stock in: {in_stock or 'none right now'}. Which option do you want?",
                     {"product_id": prod["id"], "variations": [
                         {"id": v["id"], "option": option_of(v), "stock_status": v["stock_status"],
                          "stock_quantity": v["stock_quantity"]} for v in variations]})

    return reply(True, f"{prod['name']} is {stock_text(prod)} at {money(prod['price'])}.",
                 {"product_id": prod["id"], "stock_status": prod["stock_status"],
                  "stock_quantity": prod["stock_quantity"], "price": prod["price"]})


# ---------------------------------------------------------------- create_order
def create_order(p):
    required = ["name", "email", "phone", "product_name"]
    missing = [f for f in required if not str(p.get(f, "")).strip()]
    if missing:
        return reply(False, f"I still need your {', '.join(missing).replace('_', ' ')}.")
    try:
        qty = max(1, int(str(p.get("quantity") or 1).strip()))
    except ValueError:
        return reply(False, "How many would you like? Please give me a number.")

    prod = find_product(p["product_name"])
    if not prod:
        return reply(False, f"I couldn't find \"{p['product_name']}\" in our store.")
    item, line, label = prod, {"product_id": prod["id"], "quantity": qty}, prod["name"]

    if prod["type"] == "variable":
        variations = woo.get(f"/products/{prod['id']}/variations", per_page=50)
        option = str(p.get("option", "")).strip().lower()
        match = next((v for v in variations if option_of(v).lower() == option), None)
        if not match:
            opts = ", ".join(option_of(v) for v in variations if v["stock_status"] == "instock")
            return reply(False, f"Which option of {prod['name']} would you like? Available: {opts}.")
        item, line["variation_id"], label = match, match["id"], f"{prod['name']} ({option_of(match)})"

    if item["stock_status"] != "instock":
        return reply(False, f"Sorry, {label} is out of stock right now.")
    if item.get("stock_quantity") is not None and qty > item["stock_quantity"]:
        return reply(False, f"We only have {item['stock_quantity']} of {label} left. Want that many instead?")

    first, _, last = p["name"].strip().partition(" ")
    order = woo.post("/orders", {
        "status": "pending", "set_paid": False,
        "billing": {"first_name": first, "last_name": last, "email": p["email"].strip(), "phone": p["phone"].strip()},
        "line_items": [line],
        "customer_note": "Created by the AI support agent.",
    })
    return reply(True, f"Done! Order #{order['number']} for {qty} x {label} (total {money(order['total'])}) is created. "
                       f"It's saved as pending payment and our team will send the payment link to {p['email'].strip()}.",
                 {"order_id": order["id"], "total": order["total"], "payment_url": order.get("payment_url")})


# ---------------------------------------------------------------- business hours
def is_open(now=None):
    tz = ZoneInfo(os.environ.get("STORE_TZ", "America/New_York"))
    now = now or datetime.now(tz)
    days = [d.strip() for d in os.environ.get("BUSINESS_DAYS", "1,2,3,4,5").split(",")]
    hhmm = int(now.strftime("%H%M"))
    return (str(now.isoweekday()) in days
            and int(os.environ.get("BUSINESS_OPEN", "0900")) <= hhmm < int(os.environ.get("BUSINESS_CLOSE", "1700")))


def hours_text():
    days = [int(d) for d in os.environ.get("BUSINESS_DAYS", "1,2,3,4,5").split(",")]
    o, c = os.environ.get("BUSINESS_OPEN", "0900"), os.environ.get("BUSINESS_CLOSE", "1700")
    span = f"{DAY_NAMES[days[0]-1]}-{DAY_NAMES[days[-1]-1]}" if len(days) > 1 else DAY_NAMES[days[0]-1]
    return f"{span} {o[:2]}:{o[2:]}-{c[:2]}:{c[2:]} ({os.environ.get('STORE_TZ', 'America/New_York')})"


def hours_state():
    tz = ZoneInfo(os.environ.get("STORE_TZ", "America/New_York"))
    now = datetime.now(tz)
    return {"hours": hours_text(), "now": now.strftime("%a %H:%M ") + os.environ.get("STORE_TZ", ""), "open": is_open(now)}


def business_hours(p):
    forced = os.environ.get("FORCE_ROUTE", "").strip()
    open_now = forced == "transfer" if forced in ("transfer", "message") else is_open()
    if open_now:
        return reply(True, "Our team is available now. Connecting you to a human agent.", {"open": True}, "transfer")
    return reply(True, f"We're closed right now. Our hours are {hours_text()}. "
                       "Leave your name, phone number and the reason for your call, and we'll call you back.",
                 {"open": False, "hours": hours_text()}, "message")


def callback_request(p):
    missing = [f for f in ("name", "phone") if not str(p.get(f, "")).strip()]
    if missing:
        return reply(False, f"I still need your {' and '.join(missing)}.")
    out = Path(__file__).resolve().parent.parent / "data" / "callbacks.jsonl"
    out.parent.mkdir(exist_ok=True)
    with out.open("a") as f:
        f.write(json.dumps({"at": datetime.now().isoformat(timespec="seconds"), **p}) + "\n")
    return reply(True, f"Thanks {p['name'].split()[0]}! We'll call you at {p['phone']} during business hours.")


ACTIONS = {"track_order": track_order, "check_stock": check_stock, "create_order": create_order,
           "business_hours": business_hours, "callback_request": callback_request}


def handle(body):
    action = (body or {}).get("action")
    fn = ACTIONS.get(action)
    if not fn:
        return reply(False, "Sorry, I can't help with that yet.", {"error": f"unknown action: {action}"})
    try:
        return fn((body or {}).get("payload") or {})
    except Exception as e:  # Woo down, timeout, unexpected data
        print(f"[{action}] error: {e}", file=sys.stderr)
        return reply(False, "Sorry, our store system isn't responding right now. Please try again in a few minutes.",
                     {"error": str(e)[:200]})


class Handler(BaseHTTPRequestHandler):
    def _send(self, obj, code=200):
        raw = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _page(self, page):
        raw = page.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _local(self):
        """True only for requests from this machine (a tunnel adds forwarding headers)."""
        forwarded = any(self.headers.get(h) for h in ("X-Forwarded-For", "Cf-Connecting-Ip", "Forwarded"))
        return self.client_address[0] in ("127.0.0.1", "::1") and not forwarded

    def do_GET(self):
        if DEMO and self.path == "/" and DEMO_PAGE.exists():
            return self._page(DEMO_PAGE)
        if DEMO and self.path == "/demo/config":
            return self._send(hours_state())
        if DEMO and self.path == "/voice" and VOICE_PAGE.exists():  # simulated phone-call demo
            return self._page(VOICE_PAGE)
        if DEMO and self.path.split("?")[0] == "/gemini" and GEMINI_PAGE.exists():  # live call via Gemini Live
            return self._page(GEMINI_PAGE)
        self._send({"ok": True, "service": "woo-support-webhook"})

    def do_POST(self):
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        except ValueError:
            return self._send(reply(False, "Invalid JSON."), 400)
        if DEMO and self.path == "/demo/config":  # demo only: change business hours live
            for k in ("STORE_TZ", "BUSINESS_DAYS", "BUSINESS_OPEN", "BUSINESS_CLOSE"):
                if body.get(k):
                    os.environ[k] = str(body[k])
            return self._send(hours_state())
        if DEMO and self.path == "/gemini/session":  # ephemeral token: local browser only
            if not self._local():
                return self._send({"error": "local only"}, 403)
            try:
                return self._send(gemini_live.session())
            except gemini_live.GeminiError as e:
                print(f"[gemini] {e}", file=sys.stderr)
                return self._send({"error": str(e)}, 502)
        if DEMO and self.path == "/gemini/tool":
            woo_mod.TRACE.calls = []
            result = gemini_live.tool_call(body, handle)
            return self._send({**result, "debug": {"woo_calls": woo_mod.TRACE.calls}})
        if self.path.rstrip("/") == "/vapi":  # Vapi voice agent (see docs/vapi-setup.md)
            secret = os.environ.get("VAPI_SECRET", "")
            if secret and self.headers.get("x-vapi-secret") != secret:
                return self._send({"error": "unauthorized"}, 401)
            woo_mod.TRACE.calls = []
            result = handle_vapi(body, handle)
            if DEMO and result:  # not part of Vapi's contract: shows which Woo API calls were made
                result = {**result, "debug": {"woo_calls": woo_mod.TRACE.calls}}
            return self._send(result)
        woo_mod.TRACE.calls = []
        result = handle(body)
        if DEMO:  # not part of the contract: shows which Woo API calls were made
            result = {**result, "debug": {"woo_calls": woo_mod.TRACE.calls}}
        print(f"{body.get('action')}: ok={result['ok']} route={result['route']}")
        self._send(result)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    port = int(sys.argv[sys.argv.index("--port") + 1]) if "--port" in sys.argv else 8787
    print(f"Webhook listening on http://localhost:{port}  (Woo: {woo.base})")
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
