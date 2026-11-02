#!/usr/bin/env python3
"""Send Vapi-shaped tool calls to the /vapi endpoint and check the replies.

Usage: python3 scripts/test_vapi.py [SERVER_URL]   (default http://localhost:8787)
Covers both payload shapes Vapi uses (toolCallList and toolWithToolCallList), string arguments,
the transfer/callback hints, end-of-call reports and the optional shared secret.
"""
import json, os, sys, urllib.error, urllib.request
from woo import Woo, load_env

load_env()
base = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8787").rstrip("/")
url = base + "/vapi"
SECRET = os.environ.get("VAPI_SECRET", "")

orders = Woo().get("/orders", search="sara.lee@example.com", per_page=1)
order_no = str(orders[0]["id"]) if orders else "1"


def post(body, secret=SECRET):
    headers = {"Content-Type": "application/json"}
    if secret:
        headers["x-vapi-secret"] = secret
    req = urllib.request.Request(url, json.dumps(body).encode(), headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def tool_calls(*calls, nested=False):
    items = [{"id": f"call_{i}", "type": "function", "function": {"name": n, "arguments": a}}
             for i, (n, a) in enumerate(calls)]
    msg = {"type": "tool-calls"}
    if nested:
        msg["toolWithToolCallList"] = [{"type": "function", "toolCall": c} for c in items]
    else:
        msg["toolCallList"] = items
    return {"message": msg}


def results(res):
    return {r["toolCallId"]: r["result"] for r in res.get("results", [])}


CASES = [
    ("track_order happy path", tool_calls(("track_order", {"order_number": f"#{order_no}", "email": "sara.lee@example.com"})),
     lambda s, r: s == 200 and f"Order #{order_no}" in results(r)["call_0"]),
    ("track_order wrong email (string args)", tool_calls(("track_order", json.dumps({"order_number": order_no, "email": "x@y.com"}))),
     lambda s, r: s == 200 and "couldn't find" in results(r)["call_0"]),
    ("check_stock variable product", tool_calls(("check_stock", {"product_name": "hoodie"})),
     lambda s, r: s == 200 and "Which option" in results(r)["call_0"]),
    ("two calls, nested shape", tool_calls(("check_stock", {"product_name": "coffee mug"}),
                                           ("check_stock", {"product_name": "trucker cap"}), nested=True),
     lambda s, r: s == 200 and len(results(r)) == 2 and "out of stock" in results(r)["call_1"]),
    ("business_hours gives next step", tool_calls(("business_hours", {})),
     lambda s, r: s == 200 and "NEXT STEP" in results(r)["call_0"]),
    ("callback_request", tool_calls(("callback_request", {"name": "Jane Roe", "phone": "+1 555 0110", "reason": "Bulk order"})),
     lambda s, r: s == 200 and "call you" in results(r)["call_0"]),
    ("unknown tool", tool_calls(("dance", {})),
     lambda s, r: s == 200 and "can't help" in results(r)["call_0"]),
    ("end-of-call report acknowledged", {"message": {"type": "end-of-call-report", "endedReason": "customer-ended-call",
                                                     "call": {"id": "test"}, "analysis": {"summary": "Test call."}}},
     lambda s, r: s == 200 and r == {}),
    ("status update ignored", {"message": {"type": "status-update", "status": "in-progress"}},
     lambda s, r: s == 200 and r == {}),
]
if SECRET:
    CASES.append(("wrong secret rejected", None, None))

failures = 0
for title, body, check in CASES:
    if body is None:
        status, res = post(tool_calls(("business_hours", {})), secret="wrong")
        good = status == 401
    else:
        status, res = post(body)
        good = check(status, res)
    failures += not good
    shown = " | ".join(results(res).values()) if isinstance(res, dict) and "results" in res else res
    print(f"{'PASS' if good else 'FAIL'}  {title:38} {str(shown)[:110]}")

print(f"\n{'ALL VAPI CASES PASSED' if not failures else f'{failures} CASE(S) FAILED'}  ({url})")
sys.exit(1 if failures else 0)
