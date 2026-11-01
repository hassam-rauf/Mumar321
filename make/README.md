# Make blueprint — NEEDS MANUAL REVIEW

`blueprint.json` is hand-generated from [`docs/make-scenario.md`](../docs/make-scenario.md) and has
not been round-tripped through Make. Treat the guide as the source of truth.

After **Scenarios → Create → ⋯ → Import blueprint**:

1. **Module 1 (webhook):** create/select the `woo-support` hook and re-determine the data structure.
2. **Module 2 (config):** set `woo_url` and your business hours.
3. **Every HTTP module:** select your Basic auth key (`ck_` / `cs_`).
4. **Routers 3, 11, 21, 25, 31, 35, 41:** any route named "(MARK AS FALLBACK ROUTE)" must be set
   as the fallback route (route ⋯ → *Set as fallback*). Otherwise two responses can fire.
5. **Route `callback_request`:** add *Google Sheets → Add a row* (or an email) before module 51.
6. Re-check each filter operator and every pill (Make may drop mappings it can't resolve).
7. Run `python3 scripts/test_webhook.py <webhook-url>` — all cases should PASS.
