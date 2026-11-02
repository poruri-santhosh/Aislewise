# Aislewise

### Commerce that feels effortless. Insights that move inventory.

**Aislewise** is the working product identity for an integrated shopping and retail-insights experience. It brings a browsable storefront, inventory-aware shopping flows, and a practical product analytics pipeline together in one cohesive application.

> **A product concept, built to demonstrate the full journey:** help shoppers discover products, give operators useful signals about catalog performance, and connect the experience to real application data.

| Explore | Understand | Improve |
|---|---|---|
| Search, compare, and shop in a responsive storefront | Connect catalog, inventory, and product-view data | Turn repeatable analysis into clear portfolio insights |

**[Open the storefront](https://amazon-clone-qcf3bfs86-porurisanthosh674-5041.vercel.app)** · **Streamlit-ready interactive analytics dashboard** · **Built with Flask, PostgreSQL, and Python**

> **Independent demo:** Aislewise is not affiliated with or endorsed by Amazon. The current storefront is an Amazon-inspired prototype, not a production retail service. Sample reviews are synthetic demo data, not verified customer feedback. “Aislewise” is a working name; verify name and trademark availability before commercial use.

## Product capabilities

| Layer | Technology | Purpose |
|---|---|---|
| Storefront | HTML, CSS, JavaScript | Responsive shopping experience and interactive catalog |
| Web application | Python, Flask | Store pages, APIs, sessions, authentication, cart, wishlist, and checkout |
| Database | PostgreSQL on Neon | Persistent catalog, customer, traffic, review, inventory, and order data |
| Analytics | Python, Pandas, Matplotlib | CSV extraction, data-quality checks, EDA, portfolio segmentation, and charts |
| Analytics UI | Streamlit | Interactive snapshot dashboard, filters, charts, and CSV downloads |

- Search, autocomplete, category filters, sorting, and product detail views
- Product ratings, customer reviews, and review submission
- Session-aware account flows, demo account, cart, saved items, and wishlist
- Checkout, delivery options, order history, and package tracking
- Customer support interface and responsive storefront layout
- A Python analytics workflow for product traffic, portfolio segmentation, and visual reporting
- A separately deployable Streamlit dashboard for interactive product analysis

## Architecture

### Commerce application

The storefront runs as a Flask application on Vercel. PostgreSQL on Neon is the source of truth for catalog, customer, inventory, traffic, and order data. Jinja templates render the web experience; the browser calls Flask routes for catalog and shopping actions. A separate Streamlit app reads only the committed analytics snapshots and report images; it does not connect to Neon and needs no database secrets.

```mermaid
flowchart LR
    shopper["Shopper<br/>Web browser"] -->|HTTPS| vercel["Vercel<br/>deployment + routing"]
    vercel -->|Page and API requests| flask["Flask application<br/>app.py"]
    flask -->|Render| templates["Jinja templates<br/>templates/index.html"]
    templates -->|HTML and JavaScript| shopper
    flask -->|Parameterized SQL<br/>psycopg2 + TLS| postgres[("Neon PostgreSQL")]
    snapshot["Bundled analytics data<br/>data/ + reports/"] -->|Read-only CSV and chart files| dashboard["Streamlit dashboard<br/>streamlit_app.py"]

    subgraph appdata["Application data"]
        catalog["catalog<br/>products, categories, reviews"]
        customers["customers<br/>profiles, carts, wishlists"]
        inventory["retail_inventory<br/>daily stock snapshots"]
        sales["retail_sales<br/>orders and order items"]
        traffic["retail_traffic<br/>product-view events"]
    end
    postgres --- catalog
    postgres --- customers
    postgres --- inventory
    postgres --- sales
    postgres --- traffic

    classDef experience fill:#eaf3ff,stroke:#3674b5,color:#14385a
    classDef service fill:#f2ecff,stroke:#7953b5,color:#38215b
    classDef storage fill:#e7f7f1,stroke:#23836a,color:#164b3c
    class shopper,templates,dashboard experience
    class vercel,flask service
    class postgres,catalog,customers,inventory,sales,traffic,snapshot storage
```

### Product intelligence pipeline

Analytics is an offline, reproducible workflow—not a request-time dependency of the storefront. Export scripts take database snapshots to CSV; Pandas analysis writes derived datasets, findings, and charts.

```mermaid
flowchart LR
    db[("Neon PostgreSQL<br/>catalog + views + reviews")] -->|Explicit export scripts| raw["Raw CSV snapshots<br/>data/raw/"]
    raw --> quality["Data quality checks<br/>completeness + distributions"]
    raw --> portfolio["Portfolio analysis<br/>rating and view segments"]
    raw --> reviews["Review analysis<br/>at-risk sample"]
    quality --> derived["Processed insights<br/>data/processed/"]
    portfolio --> derived
    reviews --> derived
    quality --> charts["Visual reports<br/>reports/visualisations/"]
    portfolio --> charts
    derived --> report["Executive summary<br/>reports/PROJECT_SUMMARY_REPORT.md"]
    charts --> report

    classDef source fill:#e7f7f1,stroke:#23836a,color:#164b3c
    classDef process fill:#eaf3ff,stroke:#3674b5,color:#14385a
    classDef output fill:#fff3df,stroke:#c47b16,color:#65400c
    class db,raw source
    class quality,portfolio,reviews process
    class derived,charts,report output
```

The raw product CSV is an analytics snapshot, not the application's live database. The product export combines catalog and glance-view data; the review export joins product, traffic, and review data. Pandas reads these snapshots for repeatable analysis. The included sample has **79 products** and fields `asin`, `product_title`, `total_views`, `average_rating`, and `standard_price`.

### Inventory-aware checkout

Stock is read from the latest inventory snapshot for each product. Checkout locks the matching snapshot rows, checks requested quantities, and records the stock decrement and order in the same database transaction.

```mermaid
sequenceDiagram
    participant Shopper
    participant Storefront
    participant Flask
    participant Database
    Shopper->>Storefront: Submit checkout
    Storefront->>Flask: POST checkout
    Flask->>Database: Lock latest inventory rows
    Database-->>Flask: Available units
    alt Stock is sufficient
        Flask->>Database: Decrement stock and create order
        Flask->>Database: Commit transaction
        Database-->>Flask: Order saved
        Flask-->>Storefront: Order confirmation
        Storefront-->>Shopper: Show confirmation
    else Stock is insufficient
        Flask-->>Storefront: Return stock error
        Storefront-->>Shopper: Explain availability
    end
```

The current sample review export is synthetic demo data and should be treated as an example dataset, not verified customer feedback.

### What the sample says

These are reproducible findings from [`data/raw/product_views_analysis.csv`](data/raw/product_views_analysis.csv), a 79-product sample snapshot—not live sales, verified customer behavior, or a complete inventory feed. The segmentation thresholds are inclusive: **high traffic ≥ 20 views** and **high rating ≥ 4.2**.

| Sample finding | Evidence | Suggested operator action |
|---|---|---|
| At Risk | 27 products have at least 20 recorded views and a product-level rating below 4.2. Studio Headphones Model 16 is rated 3.5 with 33 views. | Audit listing accuracy, quality signals, and feedback before increasing promotion. Individual review data is synthetic and must not be treated as customer evidence. |
| Hidden Gems | 17 products meet the rating gate but have fewer than 20 recorded views. The MacBook Air sample row is rated 4.9 with 0 recorded views. | Validate event coverage and ASIN joins first; then consider a measured discoverability experiment. |
| Stars | 35 products meet both gates. The iPhone 15 Pro Max has 2,803 views and a 4.8 product-level rating. | Protect availability and listing quality; test cross-sell opportunities. |
| No recorded views | 15 products have zero views in this extract. | Investigate tracking, reporting period, and catalog visibility before inferring no demand. |
| Price is not a useful single lever in this sample | The report's price–views Pearson correlation is −0.0571. This is descriptive association, not causation. | Test merchandising and discovery changes instead of assuming price reductions will lift traffic. |

Inventory quantities, conversion, revenue, and returns are not columns in this CSV, so this snapshot cannot identify specific inventory shortages or prove the effect of a business action. See the [EDA report](reports/PROJECT_SUMMARY_REPORT.md) for additional methodology, review-sample caveats, and limitations.

### Walkthrough

1. Open the [hosted storefront](https://amazon-clone-qcf3bfs86-porurisanthosh674-5041.vercel.app) and explore search, category filters, and a product detail page. Checkout availability depends on the hosted database's current inventory.
2. Follow the [local setup](#run-it-locally) to seed a database you control, then try cart, wishlist, and checkout flows with that demo data.
3. Review the [portfolio segmentation chart](reports/visualisations/SEGMENTATION.png), [traffic distribution](reports/visualisations/product_views_distribution.png), and [executive findings](reports/PROJECT_SUMMARY_REPORT.md).

No screen-recorded product demo is currently included; this walkthrough is a repeatable click-through guide rather than a claim that a video exists.

### Analytics visuals

All generated charts are saved in [`reports/visualisations/`](reports/visualisations/).

#### Portfolio segmentation

Products are grouped using two explicit gates: high rating is **≥ 4.2** and high traffic is **≥ 20 views**.

![Product portfolio segmentation matrix](reports/visualisations/SEGMENTATION.png)

#### Traffic distribution and outlier check

The boxplot applies the 1.5×IQR outlier rule. The histogram zooms into the 0–100-view range so the bulk of products is visible beside high-traffic outliers.

![Product views boxplot](reports/visualisations/product_views_boxplot.png)

![Product views distribution](reports/visualisations/product_views_distribution.png)

#### Price, traffic, and rating relationships

The correlation heatmap and scatter plot summarize linear association in this dataset; correlation is descriptive and does not imply causation.

![Product metric correlation heatmap](reports/visualisations/product_metrics_correlation.png)

![Product price versus views](reports/visualisations/product_price_vs_views.png)

See the [executive EDA report](reports/PROJECT_SUMMARY_REPORT.md) for findings, segment counts, review-audit caveats, and recommended actions.

## Data model

The schema is defined in [`schema.sql`](schema.sql). The application and analysis scripts use these logical areas:

| Schema | Example tables | Role |
|---|---|---|
| `catalog` | `dim_products`, `dim_categories`, `dim_reviews` | Product catalog, categories, and reviews |
| `customers` | `dim_customers`, `cart_items`, `wishlists` | Customer profiles and shopping state |
| `retail_traffic` | `fact_glance_views` | Product traffic events used in analytics |
| `retail_inventory` | `fact_fba_inventory_daily` | Inventory availability |
| `retail_sales` | `fact_orders`, `fact_order_items` | Order and line-item records |
| `fulfillment` | `dim_fulfillment_centers` | Fulfillment center reference data |

## Repository layout

```text
.
├── app.py                         # Flask application
├── streamlit_app.py               # Interactive, snapshot-based analytics dashboard
├── .streamlit/
│   └── config.toml                # Aislewise dashboard theme
├── vercel.json                    # Vercel function configuration
├── templates/
│   └── index.html                 # Storefront UI
├── data/
│   ├── raw/                       # Source analytics CSV snapshot
│   └── processed/                 # Segmentation and review CSV outputs
├── eda/
│   ├── portfolio.py               # Shared, tested segmentation rules
│   ├── visualisations/            # Chart-generation scripts
│   └── *.py                       # EDA, exports, and portfolio analysis
├── tests/
│   └── test_analytics_snapshot.py # Offline analytics tests (no database)
├── reports/
│   ├── visualisations/            # Generated PNG charts embedded above
│   └── PROJECT_SUMMARY_REPORT.md  # Executive analysis report
├── schema.sql                     # PostgreSQL DDL
├── seed_data.py                  # Demo database seeding
├── requirements.txt              # Storefront dependencies
└── requirements-eda.txt          # Analytics dependencies
```

## Run it locally

### 1. Requirements

- Python 3.10 or newer
- A PostgreSQL database (Neon is used by the hosted demo)
- Optional: `psql` to initialize the schema from the command line

### 2. Install dependencies and configure environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip install -r requirements-eda.txt
Copy-Item .env.example .env
```

Edit `.env` and set your own values:

```dotenv
DATABASE_URL=postgresql://USER:PASSWORD@HOST/DATABASE?sslmode=require
FLASK_SECRET_KEY=replace-with-a-long-random-secret
FLASK_DEBUG=false
```

Generate a session secret with:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

Keep real credentials in `.env` or the hosting provider's secret manager. **Never commit `.env` or put real connection strings in Python, notebooks, screenshots, or documentation.** The repository ignores `.env`; `.env.example` contains placeholders only.

### 3. Initialize and seed the database

Create the database tables using [`schema.sql`](schema.sql), then load demo records with [`seed_data.py`](seed_data.py). Both use the `DATABASE_URL` from `.env`. Run these only against a development database you control.

```powershell
psql $env:DATABASE_URL -f schema.sql
python seed_data.py
```

### 4. Start the web application

```powershell
python app.py
```

Open <http://127.0.0.1:5000>.

### 5. Run the analytics workflow

The EDA scripts use paths relative to the repository, so run from the project root. The database export steps are optional if you want to use the included CSV snapshots.

```powershell
# Optional: refresh the raw product/traffic snapshot from Neon
python eda/export_product_views.py

# Inspect, validate, and segment the CSV snapshot
python eda/01_data_understanding.py
python eda/02_data_quality.py
python eda/03_univariate_analysis.py
python eda/05_actionable_insights.py
python eda/find_at_risk.py

# Optional: export the at-risk product review sample from Neon
python eda/export_reviews_analysis.py
python eda/low_rated_reviews.py

# Generate all PNG charts
python eda/visualisations/boxplots.py
python eda/visualisations/distributions.py
python eda/visualisations/ratings_analysis.py
python eda/visualisations/views_vs_price.py
python eda/segmentation.py
```

Outputs:

- Raw product snapshot: `data/raw/product_views_analysis.csv`
- Segmentation and review extracts: `data/processed/`
- Generated chart images: `reports/visualisations/`

### 6. Tests

```powershell
python -m unittest discover -s tests -v
```

The offline analytics suite currently has **6 automated tests**. It checks the checked-in snapshot's schema and 79-row size, unique product IDs and valid metrics, inclusive segment-threshold edge cases, expected segment totals (35 Stars, 17 Hidden Gems, 27 At Risk, 0 Dead Weight), zero-view/high-rating handling, and that the Streamlit dashboard renders without errors. These tests read the local CSV and do not require a database.

The separate [`test_suite.py`](test_suite.py) contains **13 database integration checks** for storefront, catalog, search, cart, wishlist, customer updates, reviews, checkout, orders, and cancellation. It writes customer, cart, review, order, and inventory data; run it only against a disposable, seeded development database, never production:

```powershell
python test_suite.py
```

The integration checks have not been run as part of this README update. No pass/fail result is claimed for them.

## Publish the analytics dashboard on Streamlit Community Cloud

The Streamlit dashboard is a separate app from the Flask/Vercel storefront. It reads the checked-in product snapshot and saved charts, so it requires no Neon connection string, Vercel environment variables, or database secrets. Keep the GitHub repository accessible to the Streamlit account that will deploy it.

### Run locally

From the repository root:

```powershell
python -m pip install -r requirements.txt
python -m streamlit run streamlit_app.py
```

The dashboard includes interactive portfolio, distribution, and relationship charts; filters for product, segment, rating, price, and recorded views; a downloadable filtered CSV; committed report-image previews; and a clearly labeled synthetic-review sample. All charts use the bundled snapshot and respond to the active filters.

### Deploy from GitHub

1. Push the repository to GitHub and sign in to [Streamlit Community Cloud](https://share.streamlit.io/).
2. Select **Create app**, choose `poruri-santhosh/AMAZON-CLONE`, branch `main`, and main file path `streamlit_app.py`.
3. Keep the repository root as the app working directory. No secrets or custom install command are required; Streamlit installs the dependencies from the root `requirements.txt`.
4. Deploy. The public URL is issued by Streamlit Community Cloud after the build completes.

On each app reboot, Streamlit installs the declared root dependencies. The CSV snapshots and chart PNGs must remain committed and within the repository, because they are the dashboard's data inputs. To refresh them, run the documented EDA workflow, review the output and synthetic-data caveats, then commit the intended assets.

## Deploy to Vercel

The repository root is the Vercel project root. Vercel detects the Flask application exported as `app` from `app.py`; `vercel.json` ensures the Jinja templates are included in the function bundle. Do not set the Vercel Root Directory to `api` or install `requirements-eda.txt` for the storefront.

### Configure the project

1. Create/configure the PostgreSQL database and apply `schema.sql`. Seed it with `python seed_data.py` if it does not already contain the catalog and demo records.
2. In the Vercel project, set these **Production** environment variables under **Settings → Environment Variables**:
   - `DATABASE_URL`: the PostgreSQL/Neon connection URL. Use a URL reachable from Vercel and allow SSL; the app connects with `sslmode=require`.
   - `FLASK_SECRET_KEY`: a long, random secret unique to this deployment. Generate one with `python -c "import secrets; print(secrets.token_hex(32))"`.
3. If deploying from Git, import the repository `poruri-santhosh/AMAZON-CLONE` and leave **Root Directory** at the repository root (the default). Leave the Framework Preset on automatic detection and do not add a custom build command.

The app intentionally fails during Vercel startup if `FLASK_SECRET_KEY` is missing. If database configuration is missing or incorrect, storefront requests cannot load; verify `DATABASE_URL`, the schema, and database connectivity before deploying.

### Deploy from the terminal

Run these commands from the repository root after installing the storefront dependencies:

```powershell
python -m pip install -r requirements.txt
vercel login
vercel link
vercel
vercel --prod
```

During `vercel link`, select the existing `porurisanthosh674-5041/amazon-clone` project. Configure the environment variables in the Vercel dashboard before promoting a deployment to production. To test a preview deployment (`vercel`) against the database, add the variables to the Preview environment too; use a development database there when possible. Check the homepage and `/api/products` before running `vercel --prod`. Each deployment needs the correct environment variables enabled for its target environment.

After deployment, verify the homepage and `/api/products`. Confirm product availability against the latest inventory snapshot in the configured database. Do not commit `.env` or paste database credentials into source files or chat.

Do not commit environment secrets. The analytics CSV snapshots and report images are committed as project/demo assets; refresh them only from a database you are authorized to query.

## Brand and attribution

Aislewise is the working product identity used in this README; it does not change the current storefront UI branding. The interface is an independent Amazon-inspired demonstration and is not affiliated with Amazon. Amazon and other third-party names and marks belong to their respective owners. Review the included assets and data before any public or commercial launch, and add an appropriate license before redistributing this code.
