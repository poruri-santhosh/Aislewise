# Aislewise

### Commerce that feels effortless. Insights that move inventory.

Aislewise brings a polished retail storefront and a practical analytics workspace together. Shoppers can browse and search a broad catalog, manage a cart and wishlist, and explore an inventory-aware checkout experience. Operators can analyze product performance, sales, customer segments, traffic, inventory, reviews, and fulfillment through an interactive dashboard.

**[Explore the storefront](https://amazon-clone-phi-flax.vercel.app)** · **Analytics:** run `streamlit_app.py` locally or deploy it to Streamlit Community Cloud.

> **Demo data:** The bundled catalog and retail activity are synthetic and intended to demonstrate the product experience and analytics workflow. They do not represent actual customers, orders, or retail performance. Checkout and payment are demonstrations, not real payment processing.
>
> **Independent product:** Aislewise is an Amazon-inspired portfolio product, not an Amazon service and not affiliated with or endorsed by Amazon. “Aislewise” is a working product name; confirm name and trademark availability before commercial use.

## The product

- **A considered shopping experience:** searchable catalog, product pages, cart, saved items, wishlist, and inventory-aware demo checkout.
- **Product intelligence:** portfolio segments, category and brand performance, recorded traffic, sales, discount bands, and ratings.
- **Customer and commerce insights:** customer-segment summaries, order trends, purchase frequency, and item-line revenue.
- **Inventory visibility:** on-hand units, fulfillment-center summaries, stockout monitoring, and source-data quality checks.
- **Reproducible analytics:** read-only PostgreSQL extraction, privacy-safe aggregation, DuckDB analysis, and generated visual reports.
- **Fast interactive dashboard:** cached analytics with category, brand, segment, price, rating, traffic, customer-segment, and date filters.

## Analytics dataset

The dashboard uses a versioned offline snapshot from the Aislewise demo database. This lets the analytics experience run without a database connection. The counts below describe the snapshot generated on **November 2, 2026**; refreshing the source can change them.

| Source table | Rows |
|---|---:|
| `catalog.dim_products` | 8,079 |
| `customers.dim_customers` | 5,204 |
| `fulfillment.dim_fulfillment_centers` | 57 |
| `retail_traffic.fact_glance_views` | 40,614 |
| `retail_sales.fact_orders` | 8,176 |
| `retail_sales.fact_order_items` | 15,480 |
| `retail_inventory.fact_fba_inventory_daily` | 21,590 |
| `catalog.dim_reviews` | 4,280 |
| `customers.cart_items` | 2,151 |
| `customers.wishlists` | 2,071 |
| **Total records across these ten tables** | **107,702** |

These are counts from different entity and event tables, not a count of unique customers. The published analytics bundle contains product attributes and grouped or product-level aggregates. It excludes customer identifiers and contact details, raw order records, tracking details, reviewer identities, and review text.

### Business definitions and data quality

- Product segments use a product rating threshold of **4.2** and a recorded-event threshold of **20**. In the current snapshot: 35 Stars, 2,684 Hidden Gems, 27 At Risk, and 5,333 Dead Weight products.
- Recorded product views are event counts, not unique visitors. The source does not establish a compatible visitor cohort and period for conversion-rate analysis.
- Item-line `net_revenue` is a source measure, not profit. Cost data and independently verified currency are unavailable.
- Discount comparisons are descriptive; they do not prove causal lift. Orders have no fulfillment-center key, so sales are not attributed to centers.
- Data checks found no duplicate keys or checked relationship/range violations. The quality report flags **875** order-total/item-line differences and **136** inventory stockout-flag discrepancies. Source values are retained rather than silently altered.

See the [data dictionary](docs/DATA_DICTIONARY.md), [quality report](data/analytics/data_quality.json), [snapshot manifest](data/analytics/manifest.json), and [project report](reports/PROJECT_SUMMARY_REPORT.md) for field grains, definitions, and detailed results.

## Architecture

```mermaid
flowchart LR
    shopper["Shopper browser"] -->|HTTPS| hosting["Vercel"]
    hosting --> storefront["Flask storefront and APIs"]
    storefront --> templates["Jinja interface"]
    storefront -->|TLS, parameterized SQL| postgres[("Neon PostgreSQL")]

    postgres -->|Read-only batched extraction| pipeline["Python data pipeline"]
    pipeline -->|Aggregated CSV and JSON| snapshot["Analytics snapshot"]
    snapshot --> duckdb["DuckDB analysis"]
    snapshot --> dashboard["Streamlit dashboard"]
    duckdb --> charts["Generated visual reports"]
    charts --> dashboard

    classDef service fill:#f2ecff,stroke:#7953b5,color:#38215b
    classDef data fill:#e7f7f1,stroke:#23836a,color:#164b3c
    classDef ui fill:#eaf3ff,stroke:#3674b5,color:#14385a
    class shopper,templates,dashboard ui
    class hosting,storefront,pipeline,duckdb service
    class postgres,snapshot,charts data
```

### Analytics workflow

```mermaid
flowchart TD
    database[("PostgreSQL source tables")] --> extract["Read-only batched extraction"]
    extract --> schema["Validate schema and source counts"]
    extract --> quality["Check keys, references, ranges, and reconciliations"]
    extract --> privacy["Aggregate and omit personal identifiers"]
    privacy --> bundle["Versioned CSV snapshot and JSON manifest"]
    bundle --> analysis["DuckDB product, sales, customer, traffic, and inventory analysis"]
    analysis --> tables["Derived analytics tables"]
    tables --> charts["Matplotlib and Seaborn reports"]
    bundle --> dashboard["Cached Streamlit dashboard"]
    charts --> dashboard
    quality --> dashboard
```

## Project structure

```text
.
├── app.py
├── streamlit_app.py
├── eda/
│   ├── analytics_pipeline.py
│   ├── data_loader.py
│   ├── portfolio.py
│   └── visualisations/
│       └── analytics.py
├── data/
│   └── analytics/                   # Privacy-safe, reproducible snapshot
├── docs/
│   └── DATA_DICTIONARY.md
├── reports/
│   ├── PROJECT_SUMMARY_REPORT.md
│   └── visualisations/analytics/   # Generated charts
├── tests/
│   └── test_analytics_snapshot.py
├── requirements.txt
└── requirements-eda.txt
```

### Code and dataset map

| Code or output | Inputs | Outputs or purpose |
|---|---|---|
| `eda/analytics_pipeline.py` | PostgreSQL through `app.database_connection` | Read-only extraction, validation, `data/analytics/*.csv`, manifest, quality report |
| `eda/data_loader.py` | `product_performance.csv` | Shared product frame for analysis scripts |
| `eda/01_data_understanding.py`, `02_data_quality.py`, `03_univariate_analysis.py`, `05_actionable_insights.py`, `find_at_risk.py` | Product analytics | EDA, quality summaries, and portfolio insights |
| `eda/visualisations/analytics.py` | Aggregated analytics CSVs | Reproducible report charts |
| `streamlit_app.py` | Cached snapshot, quality report, generated charts | Interactive dashboard; no database query on widget reruns |
| `tests/test_analytics_snapshot.py` | Snapshot, dashboard, optional read-only database check | Data integrity, privacy, analytics, visualization, and UI tests |

## Visual report previews

Charts are generated directly from the project dataset:

![Aislewise product portfolio](reports/visualisations/analytics/product_segments.png)

![Category performance](reports/visualisations/analytics/category_performance.png)

![Sales trend](reports/visualisations/analytics/sales_trend.png)

![Inventory by fulfillment center](reports/visualisations/analytics/inventory_by_center.png)

## Run locally

### Install

Python 3.10+ and PostgreSQL are required to refresh the snapshot. The storefront needs the database and app secrets. The dashboard can run offline from the checked-in snapshot.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip install -r requirements-eda.txt
Copy-Item .env.example .env
```

Set secrets in your local `.env` or hosting-provider secret manager:

```dotenv
DATABASE_URL=postgresql://USER:PASSWORD@HOST/DATABASE?sslmode=require
FLASK_SECRET_KEY=replace-with-a-long-random-secret
FLASK_DEBUG=false
```

Do not commit `.env`, passwords, or real connection URLs. The analytics pipeline sets its database transaction to read-only. Do not run `seed_data.py` or the database-mutating `test_suite.py` against production.

### Refresh analytics

The pipeline validates the actual database schema, reads source tables in batches, omits personal identifiers and review text, and writes aggregated CSV/JSON outputs. It does not insert, update, delete, truncate, or recreate records.

```powershell
python eda/analytics_pipeline.py
python eda/visualisations/analytics.py
```

Optional EDA scripts use the saved analytics snapshot:

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

### Start the applications

```powershell
python app.py
python -m streamlit run streamlit_app.py
```

The Flask storefront runs at <http://127.0.0.1:5000>. Streamlit loads the checked-in snapshot; interactive filtering does not query PostgreSQL.

### Run tests

```powershell
python -m unittest discover -s tests -v
```

Tests cover source-count reconciliation, catalog completeness, privacy-safe exports, quality checks, segmentation thresholds, chart generation, and dashboard rendering. A live database test runs only when `DATABASE_URL` is configured and uses a read-only transaction. Storefront integration tests in `test_suite.py` write records and must only be run against a disposable development database.

## Deployment

### Streamlit Community Cloud

Deploy `streamlit_app.py` from the repository root. The dashboard uses the bundled privacy-safe snapshot and does not require a database secret.

### Vercel storefront

Deploy the Flask storefront from the repository root. Configure `DATABASE_URL` and `FLASK_SECRET_KEY` in Vercel for the required environments. The storefront and analytics dashboard are separate deployments.

## Brand and data notice

Aislewise is an independent portfolio product. Product imagery and demo content may come from third-party or generated sources; verify asset rights before commercial use. Synthetic analytics are for demonstration and do not describe actual consumer behavior.
