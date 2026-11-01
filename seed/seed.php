<?php
/**
 * Seeds the demo store from /seed/catalog.json and creates a REST API key.
 * Run with: wp eval-file /seed/seed.php
 * Safe to re-run: products are matched by SKU, orders are only created once.
 */
if (!function_exists('wc_get_product_id_by_sku')) {
    WP_CLI::error('WooCommerce is not active.');
}

$catalog = json_decode(file_get_contents('/seed/catalog.json'), true);
$sku_ids = [];

function demo_stock($p, $qty) {
    $p->set_manage_stock(true);
    $p->set_stock_quantity($qty);
    $p->set_stock_status($qty > 0 ? 'instock' : 'outofstock');
}

// ---------- Products ----------
foreach ($catalog['products'] as $row) {
    $existing = wc_get_product_id_by_sku($row['sku']);
    if ($existing) {
        $sku_ids[$row['sku']] = $existing;
        WP_CLI::log("exists   {$row['sku']} (#$existing)");
        if (($row['type'] ?? 'simple') === 'variable') {
            foreach ($row['variations'] as $v) {
                $sku_ids[$row['sku'] . '-' . $v['option']] = wc_get_product_id_by_sku($row['sku'] . '-' . $v['option']);
            }
        }
        continue;
    }

    if (($row['type'] ?? 'simple') === 'variable') {
        $p = new WC_Product_Variable();
        $p->set_name($row['name']);
        $p->set_sku($row['sku']);
        $attr = new WC_Product_Attribute();
        $attr->set_name($row['attribute']);
        $attr->set_options(array_column($row['variations'], 'option'));
        $attr->set_visible(true);
        $attr->set_variation(true);
        $p->set_attributes([$attr]);
        $parent_id = $p->save();

        foreach ($row['variations'] as $v) {
            $var = new WC_Product_Variation();
            $var->set_parent_id($parent_id);
            $var->set_attributes([sanitize_title($row['attribute']) => $v['option']]);
            $var->set_sku($row['sku'] . '-' . $v['option']);
            $var->set_regular_price($row['price']);
            demo_stock($var, $v['stock']);
            $sku_ids[$row['sku'] . '-' . $v['option']] = $var->save();
        }
        WC_Product_Variable::sync($parent_id);
        $sku_ids[$row['sku']] = $parent_id;
    } else {
        $p = new WC_Product_Simple();
        $p->set_name($row['name']);
        $p->set_sku($row['sku']);
        $p->set_regular_price($row['price']);
        demo_stock($p, $row['stock']);
        $sku_ids[$row['sku']] = $p->save();
    }
    WP_CLI::log("created  {$row['sku']} (#{$sku_ids[$row['sku']]})");
}

// ---------- Orders ----------
$already = wc_get_orders(['meta_key' => '_demo_seed', 'meta_value' => '1', 'limit' => -1, 'return' => 'ids']);
if ($already) {
    WP_CLI::log('Orders already seeded: #' . implode(', #', $already));
} else {
    // Don't let the seed orders reduce stock levels set above.
    add_filter('woocommerce_can_reduce_order_stock', '__return_false');
    foreach ($catalog['orders'] as $o) {
        $order = wc_create_order();
        foreach ($o['items'] as [$sku, $qty]) {
            $order->add_product(wc_get_product($sku_ids[$sku]), $qty);
        }
        $order->set_address([
            'first_name' => $o['first_name'], 'last_name' => $o['last_name'],
            'email' => $o['email'], 'phone' => $o['phone'],
            'address_1' => '100 Main St', 'city' => 'Austin', 'state' => 'TX',
            'postcode' => '78701', 'country' => 'US',
        ], 'billing');
        $order->calculate_totals();
        $order->update_meta_data('_demo_seed', '1');
        if (!empty($o['tracking'])) {
            $order->update_meta_data('_tracking_provider', $o['tracking']['carrier']);
            $order->update_meta_data('_tracking_number', $o['tracking']['number']);
        }
        $order->save();
        $order->update_status($o['status'], 'Demo seed.');
        if (!empty($o['tracking'])) {
            $order->add_order_note(
                "Shipped via {$o['tracking']['carrier']}. Tracking number: {$o['tracking']['number']}",
                1 // customer-facing note
            );
        }
        WP_CLI::log("order    #{$order->get_id()}  {$o['status']}  {$o['email']}");
    }
}

// ---------- REST API key ----------
global $wpdb;
$table = $wpdb->prefix . 'woocommerce_api_keys';
$desc = 'Voiceflow + Make demo';
if ($wpdb->get_var($wpdb->prepare("SELECT key_id FROM $table WHERE description = %s", $desc))) {
    WP_CLI::log("API key '$desc' already exists (secret is only shown once). Delete it in WooCommerce > Settings > Advanced > REST API to regenerate.");
} else {
    $ck = 'ck_' . wc_rand_hash();
    $cs = 'cs_' . wc_rand_hash();
    $wpdb->insert($table, [
        'user_id'         => 1,
        'description'     => $desc,
        'permissions'     => 'read_write', // write is needed for create_order (POST /orders)
        'consumer_key'    => wc_api_hash($ck),
        'consumer_secret' => $cs,
        'truncated_key'   => substr($ck, -7),
    ]);
    WP_CLI::log('');
    WP_CLI::success('API key created. Put these in .env:');
    WP_CLI::log("WOO_CONSUMER_KEY=$ck");
    WP_CLI::log("WOO_CONSUMER_SECRET=$cs");
}
