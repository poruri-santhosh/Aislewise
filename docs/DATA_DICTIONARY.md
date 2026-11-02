# Aislewise Data Dictionary

## Dataset overview

`data/analytics/` contains the versioned analytics snapshot generated from the Aislewise PostgreSQL database. Source records are extracted read-only and published as product attributes or grouped aggregates. Customer-level and order-level records are not included. The manifest records extraction time, source row counts, derived output counts, and privacy notes.

The snapshot contains **8,079 products** and **107,702 rows across ten source tables**. These table counts combine different entity and event types; they do not represent unique people. All retail activity in the demo dataset is synthetic and is not actual customer behavior.

## Source tables

| PostgreSQL table | Source grain | Analytics use |
|---|---|---|
| `catalog.dim_products` | One row per product ASIN | Catalog, brand, category, price, rating, and inventory join key |
| `customers.dim_customers` | One row per customer | Segment aggregates; personal/customer identifiers are not exported |
| `fulfillment.dim_fulfillment_centers` | One row per center | Center-level inventory grouping |
| `retail_traffic.fact_glance_views` | One row per recorded product-view event | Daily, product-level counts; an event is not a unique visitor |
| `retail_sales.fact_orders` | One row per order | Daily grouped order count, payment/status groups, and order totals |
| `retail_sales.fact_order_items` | One row per order line | Daily ordered units and item-line `net_revenue` summaries |
| `retail_inventory.fact_fba_inventory_daily` | One row per product/center/snapshot date | Latest-per-product stock and center inventory snapshots |
| `catalog.dim_reviews` | One row per review | Rating counts and per-product rating aggregates only |
| `customers.cart_items` | One row per customer/product/cart state | Product-level active/saved cart counts and quantities |
| `customers.wishlists` | One row per customer/product wish | Product-level wishlist-addition counts |

`catalog.dim_categories` is schema-validated and joined for product category attributes; it is not included in the ten-table record total.

## Published snapshot files

### Source-aligned and aggregated extracts

| File | Grain | Important fields |
|---|---|---|
| `products.csv` | Product | `asin`, `product_title`, `brand`, `category`, `department`, `standard_price`, `original_price`, `discount_percent`, `rating`, `rating_count`, `inventory_snapshot_date`, `latest_inventory_units`, `latest_reserved_units` |
| `traffic_daily.csv` | Date × product | `traffic_date`, `asin`, `view_events`, `buy_box_winning_view_events`, `avg_estimated_delivery_days` |
| `orders_daily.csv` | Date × order status × payment method | `order_date`, `order_status`, `payment_method`, `order_count`, `order_line_count`, `units_ordered`, `order_total_amount`, `item_line_net_revenue` |
| `product_sales.csv` | Product | `asin`, `order_line_count`, `units_sold`, `item_line_net_revenue` |
| `customer_segments.csv` | Customer segment | `customer_segment`, `customer_count`, `purchasers`, `repeat_purchasers`, `non_cancelled_orders`, `order_total_amount` |
| `inventory_by_center.csv` | Fulfillment center | Snapshot date range, center identity/location, `product_locations`, `units_in_stock`, `units_reserved`, `stockout_product_locations`, `stockout_flag_mismatches` |
| `reviews_by_product.csv` | Product with at least one review | `asin`, `review_count`, `average_review_rating`, `low_rating_review_count`, `high_rating_review_count` |
| `review_rating_distribution.csv` | Review rating | `review_rating`, `review_count` |
| `shopping_intent_by_product.csv` | Product | Active/saved cart line counts, active cart units, wishlist-addition counts |

### Derived analytics and reports

| File | Grain | Measures |
|---|---|---|
| `product_performance.csv` | Product | Catalog data, recorded-event count, sales/item-line amount, review and shopping-intent aggregates, latest stock, and portfolio segment |
| `category_performance.csv` | Category × department | Product count, traffic events, units, item-line amount, mean product rating, inventory units |
| `brand_performance.csv` | Brand | Product count, traffic events, units, item-line amount, mean product rating |
| `discount_effectiveness.csv` | Discount band | Product count, mean events per product, units, item-line amount |
| `product_segmentation_recommendations.csv` | Product | Product performance fields and portfolio segment |
| `manifest.json` | Snapshot | Dataset version/time, source and derived row counts, privacy note |
| `data_quality.json` | Snapshot | Validated schema, source counts, check counts, and reconciliation exceptions |

Review exports omit reviewer ID/name, review title, and review text. Sales exports omit customer ID, order ID, shipping details, and tracking number. Customer intelligence is grouped by segment and includes no customer-level rows.

## Metric definitions and limitations

- **Recorded view events** count source event rows; they do not represent unique visitors.
- **Repeat purchaser** means at least two orders with a status other than `cancelled`/`canceled` in the extracted database snapshot.
- **Item-line net revenue** is the sum of source `fact_order_items.net_revenue`; it is not profit or an independently reconciled accounting measure.
- **Order total amount** and item-line net revenue are separate source measures. The snapshot reports orders whose amounts differ by more than 0.02 rather than forcing them to match.
- **Latest inventory** selects each product's latest available snapshot date, then sums that date across its fulfillment centers. Product snapshot dates can differ.
- **Stockout** in the analytical check means `units_in_stock = 0`; disagreements with `out_of_stock_flag` are reported, not silently corrected.
- **Discount bands** are descriptive categories; they do not establish discount causality or incremental lift.
- **Product segmentation** uses product rating and recorded product event count with thresholds rating ≥ 4.2 and events ≥ 20.
- **Conversion rate** is not calculated because the source does not establish a unique visitor cohort and compatible time window for order attribution.
- **Fulfillment-center sales performance** is not calculated because the order schema does not identify a fulfillment center.
- All retail behavior and review records in this demonstration dataset are synthetic; results must not be presented as actual consumer behavior.
