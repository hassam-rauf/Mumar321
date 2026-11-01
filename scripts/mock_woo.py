#!/usr/bin/env python3
"""Offline mock of the WooCommerce REST API v3 subset used by this project.

Serves seed/catalog.json with Woo-shaped JSON so scripts can be tested without Docker.
It checks that credentials are sent but does not verify OAuth signatures. Not for production.

Usage: python3 scripts/mock_woo.py [--port 8099]   then set WOO_URL=http://localhost:8099
"""
import base64, json, os, re, sys
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
from woo import load_env

load_env()
KEY = os.environ.get("WOO_CONSUMER_KEY", "ck_demo")
CATALOG = json.loads((Path(__file__).resolve().parent.parent / "seed" / "catalog.json").read_text())

PRODUCTS, VARIATIONS, ORDERS, NOTES, BY_SKU = {}, {}, {}, {}, {}
_next = iter(range(10, 10_000))


def stock(qty):
    return {"manage_stock": True, "stock_quantity": qty, "stock_status": "instock" if qty > 0 else "outofstock"}


for row in CATALOG["products"]:
    pid = next(_next)
    p = {"id": pid, "name": row["name"], "sku": row["sku"], "type": row.get("type", "simple"), "status": "publish",
         "price": row["price"], "regular_price": row["price"], "variations": [], "attributes": []}
    if p["type"] == "variable":
        p["attributes"] = [{"id": 0, "name": row["attribute"], "variation": True,
                            "options": [v["option"] for v in row["variations"]]}]
        p.update(stock(0) | {"manage_stock": False, "stock_quantity": None})
        VARIATIONS[pid] = []
        for v in row["variations"]:
            vid = next(_next)
            var = {"id": vid, "sku": f'{row["sku"]}-{v["option"]}', "price": row["price"],
                   "attributes": [{"id": 0, "name": row["attribute"], "option": v["option"]}], **stock(v["stock"])}
            VARIATIONS[pid].append(var)
            p["variations"].append(vid)
            BY_SKU[var["sku"]] = (row["name"] + " - " + v["option"], var, pid)
        p["stock_status"] = "instock" if any(v["stock_quantity"] for v in VARIATIONS[pid]) else "outofstock"
    else:
        p.update(stock(row["stock"]))
    PRODUCTS[pid] = p
    BY_SKU[row["sku"]] = (row["name"], p, None)


def make_order(oid, status, billing, items, created):
    lines, total = [], 0.0
    for name, item, parent, qty in items:
        sub = float(item["price"]) * qty
        total += sub
        lines.append({"id": next(_next), "name": name, "product_id": parent or item["id"],
                      "variation_id": item["id"] if parent else 0, "quantity": qty, "total": f"{sub:.2f}"})
    return {"id": oid, "number": str(oid), "status": status, "currency": "USD",
            "date_created": created.strftime("%Y-%m-%dT%H:%M:%S"), "total": f"{total:.2f}",
            "billing": billing, "line_items": lines, "meta_data": [],
            "payment_url": f"http://localhost/checkout/order-pay/{oid}/?pay_for_order=true&key=wc_order_demo{oid}"}


for i, o in enumerate(CATALOG["orders"]):
    oid = next(_next)
    items = [(BY_SKU[s][0], BY_SKU[s][1], BY_SKU[s][2], q) for s, q in o["items"]]
    billing = {"first_name": o["first_name"], "last_name": o["last_name"], "email": o["email"], "phone": o["phone"]}
    ORDERS[oid] = make_order(oid, o["status"], billing, items, datetime.now() - timedelta(days=10 - i * 2))
    NOTES[oid] = []
    if o.get("tracking"):
        t = o["tracking"]
        ORDERS[oid]["meta_data"] = [{"id": 1, "key": "_tracking_provider", "value": t["carrier"]},
                                    {"id": 2, "key": "_tracking_number", "value": t["number"]}]
        NOTES[oid].append({"id": next(_next), "customer_note": True,
                           "note": f'Shipped via {t["carrier"]}. Tracking number: {t["number"]}'})


def woo_error(code, message, status):
    return {"code": code, "message": message, "data": {"status": status}}, status


def route(method, path, q, body):
    one = lambda k, d=None: q.get(k, [d])[0]
    if m := re.fullmatch(r"/products", path):
        res = list(PRODUCTS.values())
        if s := one("search"):
            terms = s.lower().split()
            res = [p for p in res if all(t in p["name"].lower() for t in terms)]
        if sku := one("sku"):
            res = [p for p in res if p["sku"] == sku]
        return res[: int(one("per_page", 10))], 200
    if m := re.fullmatch(r"/products/(\d+)", path):
        p = PRODUCTS.get(int(m[1]))
        return (p, 200) if p else woo_error("woocommerce_rest_product_invalid_id", "Invalid ID.", 404)
    if m := re.fullmatch(r"/products/(\d+)/variations", path):
        return VARIATIONS.get(int(m[1]), []), 200
    if path == "/orders" and method == "GET":
        res = list(ORDERS.values())[::-1]
        if s := one("search"):
            res = [o for o in res if s.lower() in json.dumps(o["billing"]).lower()]
        return res[: int(one("per_page", 10))], 200
    if path == "/orders" and method == "POST":
        items = []
        for li in body.get("line_items", []):
            vid, pid = li.get("variation_id"), li["product_id"]
            if vid:
                var = next(v for v in VARIATIONS[pid] if v["id"] == vid)
                items.append((f'{PRODUCTS[pid]["name"]} - {var["attributes"][0]["option"]}', var, pid, li["quantity"]))
            else:
                items.append((PRODUCTS[pid]["name"], PRODUCTS[pid], None, li["quantity"]))
        oid = next(_next)
        ORDERS[oid] = make_order(oid, body.get("status", "pending"), body.get("billing", {}), items, datetime.now())
        NOTES[oid] = []
        return ORDERS[oid], 201
    if m := re.fullmatch(r"/orders/(\d+)", path):
        o = ORDERS.get(int(m[1]))
        return (o, 200) if o else woo_error("woocommerce_rest_shop_order_invalid_id", "Invalid ID.", 404)
    if m := re.fullmatch(r"/orders/(\d+)/notes", path):
        if int(m[1]) not in ORDERS:
            return woo_error("woocommerce_rest_order_invalid_id", "Invalid order ID.", 404)
        notes = NOTES[int(m[1])]
        if one("type") == "customer":
            notes = [n for n in notes if n["customer_note"]]
        return notes, 200
    return woo_error("rest_no_route", "No route was found matching the URL and request method.", 404)


class Handler(BaseHTTPRequestHandler):
    def _handle(self, method):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        auth = self.headers.get("Authorization", "")
        key = q.get("oauth_consumer_key", [None])[0] or q.get("consumer_key", [None])[0]
        if auth.startswith("Basic "):
            key = base64.b64decode(auth[6:]).decode().split(":")[0]
        if not u.path.startswith("/wp-json/wc/v3"):
            obj, code = woo_error("rest_no_route", "Not a Woo route.", 404)
        elif key != KEY:
            obj, code = woo_error("woocommerce_rest_cannot_view", "Sorry, you cannot list resources.", 401)
        else:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}") if method == "POST" else {}
            obj, code = route(method, u.path[len("/wp-json/wc/v3"):].rstrip("/"), q, body)
        raw = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        self._handle("GET")

    def do_POST(self):
        self._handle("POST")

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    port = int(sys.argv[sys.argv.index("--port") + 1]) if "--port" in sys.argv else 8099
    print(f"Mock WooCommerce on http://localhost:{port}/wp-json/wc/v3  (key: {KEY})")
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
