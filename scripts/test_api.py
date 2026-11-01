#!/usr/bin/env python3
"""Verify every WooCommerce request the Make scenario uses, before building it in Make.

Usage: python3 scripts/test_api.py [--write]     (--write also tests POST /orders)
"""
import json, sys
from woo import Woo, WooError

woo = Woo()
failures = 0


def check(title, fn):
    global failures
    print(f"\n=== {title}")
    try:
        result = fn()
        print(json.dumps(result, indent=2)[:900])
        return result
    except WooError as e:
        failures += 1
        print(f"FAILED: {e}")
    except Exception as e:  # network down, bad URL, etc.
        failures += 1
        print(f"FAILED: {type(e).__name__}: {e}")


def slim_product(p):
    return {k: p.get(k) for k in ("id", "name", "type", "sku", "price", "stock_status", "stock_quantity", "variations")}


# 1. Inventory: search by name
products = check("GET /products?search=mug", lambda: [slim_product(p) for p in woo.get("/products", search="mug", per_page=5)])

# 2. Inventory: out-of-stock product
check("GET /products?search=trucker cap", lambda: [slim_product(p) for p in woo.get("/products", search="trucker cap")])

# 3. Variable product + its variations
hoodie = check("GET /products?search=hoodie", lambda: [slim_product(p) for p in woo.get("/products", search="hoodie")])
if hoodie:
    pid = hoodie[0]["id"]
    check(f"GET /products/{pid}/variations", lambda: [
        {"id": v["id"], "sku": v["sku"], "attributes": v["attributes"], "stock_status": v["stock_status"],
         "stock_quantity": v["stock_quantity"]}
        for v in woo.get(f"/products/{pid}/variations", per_page=50)])

# 4. Order tracking: latest orders, one order, its customer notes
orders = check("GET /orders?per_page=5", lambda: [
    {"id": o["id"], "status": o["status"], "email": o["billing"]["email"]} for o in woo.get("/orders", per_page=5)])
if orders:
    oid = orders[-1]["id"]
    check(f"GET /orders/{oid}", lambda: {k: v for k, v in woo.get(f"/orders/{oid}").items()
                                         if k in ("id", "status", "date_created", "billing", "line_items", "meta_data")})
    check(f"GET /orders/{oid}/notes?type=customer", lambda: woo.get(f"/orders/{oid}/notes", type="customer"))

# 5. Not found case (expect 404)
print("\n=== GET /orders/999999 (expect 404)")
try:
    woo.get("/orders/999999")
    print("UNEXPECTED: got 200"); failures += 1
except WooError as e:
    print(f"OK, got {e.status}" if e.status == 404 else f"FAILED: {e}")
    failures += e.status != 404

# 6. Create a pending order (only with --write)
if "--write" in sys.argv and products:
    check("POST /orders (status=pending)", lambda: {k: v for k, v in woo.post("/orders", {
        "status": "pending", "set_paid": False,
        "billing": {"first_name": "Test", "last_name": "Bot", "email": "test.bot@example.com", "phone": "+1 555 0199"},
        "line_items": [{"product_id": products[0]["id"], "quantity": 1}],
        "customer_note": "Created by test_api.py",
    }).items() if k in ("id", "status", "total", "payment_url")})

print(f"\n{'ALL CHECKS PASSED' if not failures else f'{failures} CHECK(S) FAILED'}")
sys.exit(1 if failures else 0)
