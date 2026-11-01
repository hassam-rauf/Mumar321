#!/usr/bin/env bash
# One-time setup of the local demo store. Run after `docker compose up -d`.
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] && set -a && . ./.env && set +a

PORT="${WP_PORT:-8080}"
wp() { docker compose run --rm -T wpcli wp "$@"; }

echo "Waiting for WordPress files..."
until docker compose exec -T wordpress test -f /var/www/html/wp-config.php; do sleep 2; done

if ! wp core is-installed 2>/dev/null; then
  wp core install --url="http://localhost:$PORT" --title="Demo Woo Store" \
    --admin_user="${WP_ADMIN_USER:-admin}" --admin_password="${WP_ADMIN_PASSWORD:-change-me}" \
    --admin_email="${WP_ADMIN_EMAIL:-admin@example.com}" --skip-email
fi

wp rewrite structure '/%postname%/' --hard           # /wp-json/ needs pretty permalinks
wp plugin install woocommerce --activate
wp option update timezone_string "${STORE_TZ:-America/New_York}"
wp option update woocommerce_currency USD
wp option update woocommerce_default_country "US:TX"
wp option update woocommerce_onboarding_profile '{"skipped":true}' --format=json

wp eval-file /seed/seed.php

echo
echo "Store:  http://localhost:$PORT   (admin: http://localhost:$PORT/wp-admin)"
echo "Next:   copy the API key above into .env, then run: python3 scripts/test_api.py"
