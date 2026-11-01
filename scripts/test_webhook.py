#!/usr/bin/env python3
"""Send every demo conversation case to the webhook (Make URL or the local reference server).

Usage: python3 scripts/test_webhook.py [WEBHOOK_URL] [--write]
Uses WEBHOOK_URL from .env when no URL is given. --write also runs create_order.
"""
import json, os, sys, urllib.request
from woo import Woo, load_env

load_env()
args = [a for a in sys.argv[1:] if not a.startswith("--")]
url = args[0] if args else os.environ.get("WEBHOOK_URL", "http://localhost:8787")

# Find a real seeded order (with tracking) so the test works on any store.
orders = Woo().get("/orders", search="sara.lee@example.com", per_page=1)
order_no = str(orders[0]["id"]) if orders else "1"

CASES = [
    ("track_order: happy path",        "track_order",    {"order_number": f"#{order_no}", "email": "Sara.Lee@example.com"}, True),
    ("track_order: wrong email",       "track_order",    {"order_number": order_no, "email": "someone@else.com"}, False),
    ("track_order: unknown order",     "track_order",    {"order_number": "999999", "email": "sara.lee@example.com"}, False),
    ("check_stock: in stock",          "check_stock",    {"product_name": "coffee mug"}, True),
    ("check_stock: out of stock",      "check_stock",    {"product_name": "trucker cap"}, True),
    ("check_stock: variable, all",     "check_stock",    {"product_name": "hoodie"}, True),
    ("check_stock: variable, size M",  "check_stock",    {"product_name": "hoodie", "option": "m"}, True),
    ("check_stock: unknown product",   "check_stock",    {"product_name": "spaceship"}, False),
    ("create_order: out of stock",     "create_order",   {"name": "Jane Roe", "email": "jane@example.com", "phone": "+1 555 0110",
                                                          "product_name": "trucker cap", "quantity": "1"}, False),
    ("create_order: too many",         "create_order",   {"name": "Jane Roe", "email": "jane@example.com", "phone": "+1 555 0110",
                                                          "product_name": "sticker pack", "quantity": "10"}, False),
    ("business_hours",                 "business_hours", {}, True),
    ("callback_request",               "callback_request", {"name": "Jane Roe", "phone": "+1 555 0110", "reason": "Bulk order"}, True),
    ("unknown action",                 "dance",          {}, False),
]
if "--write" in sys.argv:
    CASES.append(("create_order: variable product", "create_order",
                  {"name": "Jane Roe", "email": "jane@example.com", "phone": "+1 555 0110",
                   "product_name": "hoodie", "option": "L", "quantity": "1"}, True))

failures = 0
for title, action, payload, expect_ok in CASES:
    req = urllib.request.Request(url, json.dumps({"action": action, "payload": payload}).encode(),
                                 {"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            res = json.loads(r.read())
        good = (res.get("ok") == expect_ok and isinstance(res.get("message"), str)
                and {"ok", "message", "data", "route"} <= res.keys())
    except Exception as e:
        res, good = {"error": str(e)}, False
    failures += not good
    print(f"{'PASS' if good else 'FAIL'}  {title:34} route={res.get('route')!s:8} {res.get('message', res)}")

print(f"\n{'ALL CASES PASSED' if not failures else f'{failures} CASE(S) FAILED'}  ({url})")
sys.exit(1 if failures else 0)
