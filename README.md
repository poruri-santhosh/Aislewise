# Aislewise

### Commerce that feels effortless. Insights that move inventory.

Aislewise is a retail commerce and analytics platform built to work across a broad product catalog and related customer, traffic, sales, inventory, fulfillment, and review data. Its analytics workspace combines PostgreSQL extraction, privacy-safe aggregation, DuckDB analysis, reproducible visualizations, and an interactive Streamlit dashboard.

> **Scale, stated accurately:** the current database snapshot contains **8,079 products** and **107,702 rows across the 10 extracted operational tables**. The project owner reports **80,000 additional synthetic records** across those tables. That 80,000 figure is supporting records—not 80,000 products. All data is synthetic/demo data and must not be presented as real customer or retail activity.

**[Open the storefront](https://amazon-clone-phi-flax.vercel.app)** · **Analytics dashboard:** run locally or deploy `streamlit_app.py` with Streamlit Community Cloud.

> **Independent demo:** Aislewise is an Amazon-inspired prototype, not an Amazon service, and is not affiliated with or endorsed by Amazon. Product, customer, traffic, sales, inventory, fulfillment, and review records in the demo database are synthetic. “Aislewise” is a working product name; verify name and trademark availability before commercial use.

## What the platform demonstrates

- Searchable, inventory-aware Flask storefront with catalog, cart, saved items, wishlist, and simulated checkout.
- Read-only, batched extraction from ten PostgreSQL tables; the application database is never modified by analytics refreshes.
- DuckDB-backed product, category, brand, and discount analyses.
- Customer segment, purchase frequency, orders, item-line revenue, traffic-event, inventory, fulfillment, and review-rating summaries.
- Data quality checks for schema compatibility, duplicate keys, foreign keys, required fields, numerical bounds, stockout flags, and order/item reconciliation.
- Interactive Streamlit dashboard with category, brand, product-segment, customer-segment, rating, price, recorded-event, and date filters.
- A versioned, privacy-conscious analytics bundle with no customer identifiers, contact information, raw review text, order IDs, or tracking numbers.

## Verified dataset snapshot

The checked-in dashboard bundle is an **offline snapshot** exported from the existing Neon PostgreSQL database. The figures below describe the snapshot generated on 2026-11-02; refreshing the source database will change counts and may change quality findings.

| Source table | Rows in snapshot | Owner-reported added synthetic records |
|---|---:|---:|
| `catalog.dim_products` | 8,079 | 8,000 |
| `customers.dim_customers` | 5,204 | 5,000 |
| `fulfillment.dim_fulfillment_centers` | 57 | 50 |
| `retail_traffic.fact_glance_views` | 40,614 | 33,000 |
| `retail_sales.fact_orders` | 8,176 | 7,000 |
| `retail_sales.fact_order_items` | 15,480 | 14,000 |
| `retail_inventory.fact_fba_inventory_daily` | 21,590 | 5,000 |
| `catalog.dim_reviews` | 4,280 | 4,000 |
| `customers.cart_items` | 2,151 | 2,000 |
| `customers.wishlists` | 2,071 | 1,950 |
| **Total across the 10 extracted tables** | **107,702** | **80,000** |

These are row counts from different entity and event tables and must not be interpreted as a count of unique people or products. The product catalog itself has 8,079 rows. The bundle contains product-level inventory, daily product traffic events, daily sales summaries, customer-segment aggregates, product review aggregates, and fulfillment-center inventory summaries—not raw customer or order records.

### Snapshot findings

- Product segmentation uses inclusive gates of **20 recorded view events** and **4.2 product rating**: 35 Stars, 2,684 Hidden Gems, 27 At Risk, and 5,333 Dead Weight products in this snapshot.
- The snapshot contains **40,614 recorded traffic events** across **8,064 products with at least one event**. A recorded event is not a unique visitor.
- Customer behavior is grouped by six customer segments. “Repeat purchaser” means a customer with at least two orders whose status is not cancelled; it is a snapshot count, not a retention or lifetime-value metric.
- The source contains **8,176 orders**, **15,480 item lines**, and **29,788 ordered units**. Item-line `net_revenue` totals 31,534,700.11 in source units; this is not profit. The source currency is not independently established by the extract.
- The snapshot contains **4,280 synthetic review rows**, exported only as rating aggregates.

### Data quality transparency

The extraction reported zero duplicate primary/business keys, broken product/customer/order/fulfillment references, missing required product fields, invalid product prices or ratings, negative inventory, and invalid order-item quantities/values. It also found:

- **875 orders** where `fact_orders.total_amount` differs by more than 0.02 from the sum of item-line `net_revenue`. The two fields may represent different business definitions; this is a reconciliation exception, not an automatic claim that either value is wrong.
- **136 inventory rows** where `out_of_stock_flag` does not match `units_in_stock = 0`. The source records are retained unchanged and the discrepancy is surfaced in the quality dashboard.

No profit, unique-visitor count, causal discount effect, or conversion rate is inferred. The source does not establish a visitor population and reporting period compatible with order data. Order records do not identify a fulfillment center, so sales are not attributed to centers.

See the generated [`expanded data quality report`](data/expanded/data_quality.json), [`snapshot manifest`](data/expanded/manifest.json), and [`executive analytics report`](reports/PROJECT_SUMMARY_REPORT.md) for the full check results, source counts, definitions, and limitations.

## Architecture

```mermaid
flowchart LR
    shopper["Shopper browser"] -->|HTTPS| vercel["Vercel"]
    vercel --> flask["Flask storefront and APIs"]
    flask --> templates["Jinja UI"]
    flask -->|TLS, parameterized SQL| neon[("Neon PostgreSQL")]

    neon -->|Read-only named cursors, batches| extract["Python extraction and validation"]
    extract -->|Privacy-safe CSV aggregates| bundle["data/expanded snapshot"]
    bundle -->|DuckDB SQL| analytics["Product, sales, customer, traffic, inventory, review analytics"]
    analytics --> charts["Matplotlib and Seaborn reports"]
    bundle --> dashboard["Streamlit dashboard"]
    charts --> dashboard

    classDef service fill:#f2ecff,stroke:#7953b5,color:#38215b
    classDef data fill:#e7f7f1,stroke:#23836a,color:#164b3c
    classDef ui fill:#eaf3ff,stroke:#3674b5,color:#14385a
    class shopper,templates,dashboard ui
    class vercel,flask,extract,analytics service
    class neon,bundle,charts data
```

### Analytics data flow

```mermaid
flowchart TD
    pg[("Neon PostgreSQL<br/>10 source tables")] --> extract["Read-only batched extraction"]
    extract --> schema["Validate schema and source counts"]
    extract --> quality["Audit keys, references, ranges and reconciliations"]
    extract --> privacy["Aggregate; omit customer/order identifiers and review text"]
    privacy --> csv["Versioned CSV snapshot + JSON manifest"]
    csv --> duckdb["DuckDB product/category/brand/discount queries"]
    csv --> streamlit["Cached Streamlit analytics"]
    duckdb --> derived["Derived analytical CSVs"]
    derived --> charts["Reproducible Matplotlib/Seaborn visualizations"]
    charts --> streamlit
    quality --> dashboard["Published data-quality findings"]
```

### Repository-to-dataset dependency map

| Code or output | Inputs | Outputs / use |
|---|---|---|
| `eda/expanded_pipeline.py` | Neon source tables through `app.database_connection` | `data/expanded/*.csv` (including product segmentation recommendations), `manifest.json`, `data_quality.json` |
| `eda/data_loader.py` | `product_performance.csv` | Shared product frame for EDA scripts |
| `eda/01_data_understanding.py`, `02_data_quality.py`, `03_univariate_analysis.py`, `05_actionable_insights.py`, `find_at_risk.py` | Shared expanded product frame | Console summaries, segmentation analysis, and risk insights |
| `eda/segmentation.py` | `product_segmentation_recommendations.csv` | Expanded portfolio scatter plot |
| `eda/visualisations/expanded.py` | Aggregated expanded CSVs | Expanded chart PNGs under `reports/visualisations/expanded/` |
| `eda/visualisations/*.py`, `eda/segmentation.py` | Shared expanded product frame / segmentation output | Additional expanded product plots |
| `streamlit_app.py` | Cached expanded CSVs, JSON reports, chart PNGs | Interactive analytics; no database query on widget reruns |
| `tests/test_analytics_snapshot.py` | Checked-in aggregate bundle and dashboard | Offline pipeline, privacy, quality, chart, and UI tests; optional read-only DB test |

## Analytics and metric definitions

| Area | Definition and guardrail |
|---|---|
| Product performance | Catalog rating, recorded view-event count, units ordered, item-line `net_revenue`, review aggregates, and latest available inventory by product. |
| Portfolio segments | Stars: rating ≥ 4.2 and events ≥ 20; Hidden Gems: rating ≥ 4.2 and events < 20; At Risk: rating < 4.2 and events ≥ 20; Dead Weight: rating < 4.2 and events < 20. Product traffic is event count, not people. |
| Category and brand | Product counts, recorded events, units, item-line net revenue, mean product rating, and inventory. Descriptive summaries only. |
| Customer intelligence | Counts grouped by customer segment; purchaser count and repeat-purchaser count use orders excluding cancelled statuses. Customer-level rows and identifiers are not exported. |
| Sales | Daily order counts, units, order-level amount, and item-line net revenue are kept separate; totals are not assumed to be interchangeable. No cost table exists, so profit is not calculated. |
| Traffic | Events grouped by date and product, including buy-box-winning event counts. No unique visitors or conversion rates are calculated. |
| Inventory | Latest available daily snapshot per product, summed across fulfillment centers; snapshot dates may differ by product. Stockout-flag discrepancies are reported. |
| Reviews | Per-product and rating-distribution aggregates only. Review data is synthetic; raw review text and reviewer details are excluded. |
| Fulfillment | Inventory and stockout footprint by center. Orders have no center key, so order/sales performance is not attributed to a center. |
| Discount | Units and item-line amounts grouped into catalog discount bands. Observational results do not prove discounts caused changes. |

## Visual report previews

These PNGs are generated from the expanded snapshot—not manually edited:

![Expanded product portfolio segments](reports/visualisations/expanded/product_segments.png)

![Category performance](reports/visualisations/expanded/category_performance.png)

![Daily sales and traffic reports](reports/visualisations/expanded/sales_trend.png)

![Inventory by fulfillment center](reports/visualisations/expanded/inventory_by_center.png)

The complete dashboard also includes product and brand explorers, date/category/brand/segment filters, sales and traffic tables, stockout monitoring, review aggregates, fulfillment summaries, and a data-quality tab.

## Data dictionary and storage layout

See [`docs/DATA_DICTIONARY.md`](docs/DATA_DICTIONARY.md) for source table descriptions, published dataset fields, grain, privacy, and metric definitions.

```text
.
├── app.py
├── streamlit_app.py
├── eda/
│   ├── expanded_pipeline.py
│   ├── data_loader.py
│   ├── portfolio.py
│   └── visualisations/
│       └── expanded.py
├── data/
│   └── expanded/                  # Sanitized, reproducible analytical snapshot
├── reports/
│   ├── PROJECT_SUMMARY_REPORT.md
│   └── visualisations/expanded/   # Generated expanded-dataset charts
├── tests/test_analytics_snapshot.py
├── schema.sql
├── requirements.txt
└── requirements-eda.txt
```

## Run locally

### Install and configure

Python 3.10+ and a PostgreSQL database are required for refreshing the database snapshot. The dashboard can run offline from the checked-in snapshot.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip install -r requirements-eda.txt
Copy-Item .env.example .env
```

Set secrets only in your local `.env` or hosting-provider secret manager:

```dotenv
DATABASE_URL=postgresql://USER:PASSWORD@HOST/DATABASE?sslmode=require
FLASK_SECRET_KEY=replace-with-a-long-random-secret
FLASK_DEBUG=false
```

Never commit `.env`, `.env.local`, passwords, or real connection URLs. Analytics exports contain aggregated synthetic data only. Do not run `seed_data.py` or the database-mutating `test_suite.py` against production.

### Refresh the expanded analytical bundle

The refresh requires `DATABASE_URL` and reads the database in a read-only transaction. It inspects the actual schema, streams table queries in batches, omits customer identifiers and review text, writes aggregate CSV/JSON outputs, and runs DuckDB analyses. It does not insert, update, delete, truncate, or recreate database rows.

```powershell
python eda/expanded_pipeline.py
python eda/visualisations/expanded.py
```

Optional EDA scripts use the expanded snapshot and do not need a database connection:

```powershell
python eda/01_data_understanding.py
python eda/02_data_quality.py
python eda/03_univariate_analysis.py
python eda/05_actionable_insights.py
python eda/find_at_risk.py
python eda/segmentation.py
python eda/visualisations/boxplots.py
python eda/visualisations/distributions.py
python eda/visualisations/ratings_analysis.py
python eda/visualisations/views_vs_price.py
```

### Run the Flask storefront and analytics dashboard

```powershell
python app.py
python -m streamlit run streamlit_app.py
```

The Flask app serves at <http://127.0.0.1:5000>. Streamlit loads the checked-in aggregate snapshot and uses Streamlit caching; interactive filters do not query Neon.

### Tests

```powershell
python -m unittest discover -s tests -v
```

Tests cover bundle completeness, source and aggregate reconciliation, identifier exclusion, quality exceptions, inclusive segmentation thresholds, chart generation, and Streamlit rendering. A read-only live database check runs only when `DATABASE_URL` is configured; it verifies schema-backed product completeness and traffic references. Storefront integration tests in `test_suite.py` write records and must only be run against a disposable development database.

## Publish

### Streamlit Community Cloud

Deploy `streamlit_app.py` from the repository root. The dashboard requires no database secret because it reads the checked-in, privacy-safe CSV and JSON snapshots and generated chart files. Push refreshed snapshot and chart files when publishing a new analytics release.

### Vercel storefront

The Flask storefront is deployed from the repository root. Configure `DATABASE_URL` and `FLASK_SECRET_KEY` as Vercel environment variables for the required environments. Keep Vercel's Root Directory at the repository root; the analytics refresh and Streamlit dashboard are separate from the storefront deployment.

## License and data notice

This repository is an independent portfolio demonstration. Product/catalog imagery and synthetic demo content may be sourced from third-party or generated data; verify the terms of any assets before commercial use. No real customer behavior is claimed.
