# Aislewise Retail Analytics

- **Snapshot date:** 2026-11-02
- **Dataset version:** `aislewise-retail-analytics-v1`
- **Source:** Neon PostgreSQL, read-only extraction
- **Data notice:** Retail activity and review records are synthetic demo data.

## Executive overview

The analytics snapshot contains **8,079 products** and **107,702 observed rows across ten source tables**. The published bundle provides product-level and grouped analytics without customer identifiers, raw order records, tracking details, reviewer identities, or review text.

| Metric | Snapshot result |
|---|---:|
| Products | 8,079 |
| Product categories represented | 29 |
| Brands represented | 26 |
| Recorded product-view events | 40,614 |
| Products with at least one recorded event | 8,064 |
| Orders | 8,176 |
| Order item lines | 15,480 |
| Units ordered | 29,788 |
| Item-line `net_revenue` sum (source units) | 31,534,700.11 |
| Customer rows, grouped before publication | 5,204 |
| Customers with orders excluding cancelled statuses | 4,951 |
| Repeat purchasers (2+ non-cancelled orders) | 2,040 |
| Synthetic review rows, published as aggregates | 4,280 |
| Fulfillment centers | 57 |
| Rows across ten source tables | 107,702 |

Item-line `net_revenue` is not profit; the database does not provide product cost. The source currency is not established by this export. The order and traffic windows also differ, so no conversion rate is reported.

## Product portfolio

Segments use product-level rating and recorded product-view event counts, with inclusive thresholds of rating ≥ 4.2 and events ≥ 20:

| Segment | Products | Definition |
|---|---:|---|
| Stars | 35 | Rating ≥ 4.2 and at least 20 recorded events |
| Hidden Gems | 2,684 | Rating ≥ 4.2 and fewer than 20 recorded events |
| At Risk | 27 | Rating < 4.2 and at least 20 recorded events |
| Dead Weight | 5,333 | Rating < 4.2 and fewer than 20 recorded events |
| **Total** | **8,079** | |

Traffic is a count of event rows, not unique visitors. The large low-traffic quadrants should be interpreted alongside event coverage and the demo data's synthetic nature.

## Sales, customer, and demand measures

- The source contains 8,176 order rows and 15,480 item rows.
- Summed item-line `net_revenue` is 31,534,700.11 in source units; `fact_orders.total_amount` sums to 30,754,583.75. These source values remain separate.
- Customer reports group all 5,204 customer rows by the six stored segment labels. Purchasers count customers with at least one non-cancelled order; repeat purchasers count at least two such orders.
- Traffic contains 40,614 events across 8,064 products. It is not a unique-visitor measure.
- Discount bands compare observed catalog/product outcomes descriptively; they do not prove discounts cause unit or revenue changes.

## Inventory, fulfillment, and reviews

Inventory summaries select each product's latest available inventory date and group that product's center rows. Products can have different latest dates, spanning 2026-10-14 through 2026-11-02; totals are not a single synchronized physical inventory count.

The database has 57 fulfillment-center rows. The order schema has no fulfillment-center key, so sales or delivery outcomes are not attributed to centers.

There are 4,280 synthetic review rows. Only product-level rating aggregates and counts are included in the published snapshot. Reviewer names, IDs, titles, and review text are excluded.

## Data quality results

The read-only extraction checked required columns before exporting. It reported **zero** duplicate business/primary keys, orphan product/customer/order/center references, missing required product fields, invalid product prices/ratings/discounts, negative inventory/reservations, and invalid order-item quantities/values.

Two exceptions are explicitly retained in [`data/analytics/data_quality.json`](../data/analytics/data_quality.json):

1. **875 orders** differ by more than 0.02 between `fact_orders.total_amount` and summed `fact_order_items.net_revenue`. They may have different business definitions; reconcile with the source owner before comparing them as equivalent totals.
2. **136 inventory rows** have `out_of_stock_flag` inconsistent with `units_in_stock = 0`. The pipeline surfaces but does not mutate or “correct” source data.

## Reproducible outputs

The [snapshot manifest](../data/analytics/manifest.json) records source table counts, derived row counts, dataset version, and extraction time. Derived tables use DuckDB over privacy-safe CSV extracts.

Generated visualizations are under `reports/visualisations/analytics/`:

- `product_segments.png` — portfolio segment counts.
- `category_performance.png` and `brand_performance.png` — leading categories and brands by item-line amount.
- `sales_trend.png` — daily source item-line `net_revenue`.
- `traffic_trend.png` — daily recorded traffic events.
- `inventory_by_center.png` — inventory snapshot by fulfillment center.
- `review_ratings.png` — synthetic review rating distribution.
- `discount_units.png` — observed units by catalog discount band.

Run `python eda/analytics_pipeline.py` to refresh the read-only snapshot and `python eda/visualisations/analytics.py` to regenerate the charts. See the [data dictionary](../docs/DATA_DICTIONARY.md) for field grains, privacy controls, and metric definitions.

## Limitations

- All retail behavior and review records are synthetic demo data; findings do not describe actual customer behavior.
- View events are not unique people. No compatible visitor/order cohort is available for conversion-rate calculation.
- Net revenue is not profit; costs are unavailable.
- Order totals and item-line net revenue disagree for 875 orders and require business-definition reconciliation.
- Inventory status has 136 flag disagreements and product snapshot dates are not fully synchronized.
- No order-to-fulfillment-center relationship is available for center-level sales attribution.
- Discount comparisons are observational, not causal.
