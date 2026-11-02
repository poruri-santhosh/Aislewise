"""Aislewise's interactive, snapshot-based retail analytics dashboard."""

from pathlib import Path
import json
import sys

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent
VISUALS_PATH = PROJECT_ROOT / "reports" / "visualisations"
EDA_PATH = PROJECT_ROOT / "eda"
ANALYTICS_PATH = PROJECT_ROOT / "data" / "analytics"
ANALYTICS_MANIFEST = ANALYTICS_PATH / "manifest.json"
if str(EDA_PATH) not in sys.path:
    sys.path.insert(0, str(EDA_PATH))

from portfolio import HIGH_RATING, HIGH_TRAFFIC_VIEWS

SEGMENT_COLORS = {
    "Stars (High Traffic, High Rating)": "#16856b",
    "Hidden Gems (Low Traffic, High Rating)": "#4278c5",
    "At Risk (High Traffic, Low Rating)": "#d58a27",
    "Dead Weight (Low Traffic, Low Rating)": "#b94c55",
}

st.set_page_config(
    page_title="Aislewise | Product Intelligence",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .block-container {padding-top: 2rem; padding-bottom: 3rem;}
    [data-testid="stMetric"] {
        background: #ffffff;
        border: 1px solid #e6ebf2;
        padding: 1rem 1.15rem;
        border-radius: 0.8rem;
    }
    .eyebrow {
        color: #16856b;
        font-weight: 700;
        letter-spacing: .12em;
        text-transform: uppercase;
        font-size: .75rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def format_number(value: float) -> str:
    return f"{value:,.0f}"


@st.cache_data
def load_analytics_snapshot(path: str, fingerprint: tuple[tuple[str, float], ...]) -> dict:
    """Load the pre-aggregated, privacy-safe analytics bundle."""
    del fingerprint
    root = Path(path)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    dataset = {
        "manifest": manifest,
        "quality": json.loads((root / "data_quality.json").read_text(encoding="utf-8")),
    }
    for filename in (
        "product_performance.csv",
        "category_performance.csv",
        "brand_performance.csv",
        "discount_effectiveness.csv",
        "orders_daily.csv",
        "traffic_daily.csv",
        "customer_segments.csv",
        "inventory_by_center.csv",
        "review_rating_distribution.csv",
    ):
        dataset[filename.removesuffix(".csv")] = pd.read_csv(root / filename)
    return dataset


def filter_dates(data: pd.DataFrame, column: str, selected_range: tuple) -> pd.DataFrame:
    if data.empty or not selected_range:
        return data
    dates = pd.to_datetime(data[column], errors="coerce")
    start, end = selected_range
    return data.loc[dates.between(pd.Timestamp(start), pd.Timestamp(end))]


def normalize_date_range(selected_range):
    if isinstance(selected_range, (tuple, list)) and len(selected_range) == 2:
        return selected_range
    if selected_range:
        return (selected_range, selected_range)
    return None


def apply_filters(
    data: pd.DataFrame,
    query: str,
    selected_segments: list[str],
    rating_floor: float,
    price_range: tuple[float, float],
    view_range: tuple[int, int],
) -> pd.DataFrame:
    filtered = data[
        data["segment"].isin(selected_segments)
        & data["average_rating"].ge(rating_floor)
        & data["standard_price"].between(*price_range)
        & data["total_views"].between(*view_range)
    ]
    if query:
        filtered = filtered[
            filtered["product_title"].str.contains(query, case=False, na=False)
            | filtered["asin"].str.contains(query, case=False, na=False)
        ]
    return filtered


def render_segment_chart(data: pd.DataFrame) -> None:
    fig, axis = plt.subplots(figsize=(10, 5.5))
    for segment, color in SEGMENT_COLORS.items():
        group = data[data["segment"] == segment]
        if not group.empty:
            axis.scatter(
                group["average_rating"],
                group["total_views"],
                color=color,
                label=f"{segment.split(' (')[0]} ({len(group)})",
                alpha=0.8,
                edgecolors="white",
                linewidths=0.6,
                s=65,
            )
    axis.axvline(HIGH_RATING, color="#778399", linestyle="--", linewidth=1)
    axis.axhline(HIGH_TRAFFIC_VIEWS, color="#778399", linestyle="--", linewidth=1)
    axis.set(title="Product portfolio", xlabel="Product rating", ylabel="Recorded views")
    axis.grid(alpha=0.18)
    axis.legend(frameon=False, loc="upper left")
    fig.tight_layout()
    st.pyplot(fig, width="stretch")
    plt.close(fig)


def render_distribution_charts(data: pd.DataFrame) -> None:
    views_column, rating_column = st.columns(2)
    with views_column:
        fig, axis = plt.subplots(figsize=(7, 4))
        axis.hist(data["total_views"], bins=min(20, max(5, len(data))), color="#4278c5", edgecolor="white")
        axis.set(title="Recorded views distribution", xlabel="Views", ylabel="Products")
        axis.grid(axis="y", alpha=0.18)
        fig.tight_layout()
        st.pyplot(fig, width="stretch")
        plt.close(fig)
    with rating_column:
        fig, axis = plt.subplots(figsize=(7, 4))
        axis.hist(data["average_rating"], bins=10, color="#16856b", edgecolor="white")
        axis.set(title="Product rating distribution", xlabel="Rating (0–5)", ylabel="Products")
        axis.grid(axis="y", alpha=0.18)
        fig.tight_layout()
        st.pyplot(fig, width="stretch")
        plt.close(fig)


def render_relationship_charts(data: pd.DataFrame) -> None:
    price_column, views_column = st.columns(2)
    with price_column:
        fig, axis = plt.subplots(figsize=(7, 4))
        axis.scatter(data["standard_price"], data["total_views"], color="#7357a5", alpha=0.72)
        axis.set(title="Price vs. recorded views", xlabel="Listed price (dataset units)", ylabel="Recorded views")
        axis.grid(alpha=0.18)
        fig.tight_layout()
        st.pyplot(fig, width="stretch")
        plt.close(fig)
    with views_column:
        corr = data[["total_views", "average_rating", "standard_price"]].corr()
        fig, axis = plt.subplots(figsize=(7, 4))
        image = axis.imshow(corr, cmap="PuBuGn", vmin=-1, vmax=1)
        labels = ["Views", "Rating", "Price"]
        axis.set_xticks(range(len(labels)), labels=labels)
        axis.set_yticks(range(len(labels)), labels=labels)
        for row in range(len(labels)):
            for col in range(len(labels)):
                axis.text(col, row, f"{corr.iloc[row, col]:.2f}", ha="center", va="center")
        axis.set_title("Metric correlation")
        fig.colorbar(image, ax=axis, fraction=0.046, pad=0.04)
        fig.tight_layout()
        st.pyplot(fig, width="stretch")
        plt.close(fig)


with st.sidebar:
    st.header("Aislewise analytics")
    st.caption("The dashboard uses the bundled, privacy-safe database snapshot.")

try:
    bundle_files = sorted(ANALYTICS_PATH.glob("*.csv"))
    fingerprint = tuple(
        [(path.name, path.stat().st_mtime) for path in bundle_files]
        + [("manifest.json", ANALYTICS_MANIFEST.stat().st_mtime)]
    )
    analytics_data = load_analytics_snapshot(str(ANALYTICS_PATH), fingerprint)
    products = analytics_data["product_performance"].rename(
        columns={
            "rating": "average_rating",
            "traffic_event_count": "total_views",
        }
    )
    products["segment"] = products["segment"].astype(str)
    if len(products) != int(analytics_data["manifest"]["product_rows"]):
        raise ValueError("Product rows do not match the dataset manifest.")
except (OSError, KeyError, pd.errors.ParserError, ValueError, json.JSONDecodeError) as error:
    st.error(f"Could not load the Aislewise analytics snapshot: {error}")
    st.stop()

with st.sidebar:
    st.header("Explore products")
    search_query = st.text_input("Find a product", placeholder="Product name or ASIN")
    selected_segments = st.multiselect(
        "Portfolio segments",
        options=list(SEGMENT_COLORS),
        default=list(SEGMENT_COLORS),
        format_func=lambda value: value.split(" (")[0],
    )
    minimum_rating = st.slider("Minimum rating", 0.0, 5.0, 0.0, 0.1)
    price_bounds = (
        float(products["standard_price"].min()),
        float(products["standard_price"].max()),
    )
    selected_prices = st.slider(
        "Listed price range",
        min_value=price_bounds[0],
        max_value=price_bounds[1],
        value=price_bounds,
    )
    view_bounds = (int(products["total_views"].min()), int(products["total_views"].max()))
    selected_views = st.slider(
        "Recorded view-event range",
        min_value=view_bounds[0],
        max_value=view_bounds[1],
        value=view_bounds,
    )
    category_options = sorted(products["category"].dropna().astype(str).unique()) if "category" in products else []
    selected_categories = st.multiselect("Categories", category_options, default=category_options)
    brand_options = sorted(products["brand"].dropna().astype(str).unique()) if "brand" in products else []
    selected_brands = st.multiselect("Brands", brand_options, default=brand_options)
    customer_segment_options = sorted(
        analytics_data["customer_segments"]["customer_segment"].dropna().astype(str).unique()
    )
    selected_customer_segments = st.multiselect(
        "Customer segments",
        customer_segment_options,
        default=customer_segment_options,
    )
    selected_date_range = None
    order_dates = pd.to_datetime(analytics_data["orders_daily"]["order_date"], errors="coerce").dropna()
    if not order_dates.empty:
        selected_date_range = st.date_input(
            "Order and traffic date range",
            value=(order_dates.min().date(), order_dates.max().date()),
            min_value=order_dates.min().date(),
            max_value=order_dates.max().date(),
        )
    st.divider()
    st.caption("Product segment gates: rating ≥ 4.2 and recorded view events ≥ 20.")
    st.caption(
        "Date filters apply to orders and traffic. Product filters apply to product, "
        "traffic, and inventory views; customer-segment filters apply to customer analytics."
    )

filtered_products = apply_filters(
    products,
    search_query.strip(),
    selected_segments,
    minimum_rating,
    selected_prices,
    selected_views,
)
if selected_categories and "category" in filtered_products:
    filtered_products = filtered_products[
        filtered_products["category"].astype(str).isin(selected_categories)
    ]
if selected_brands and "brand" in filtered_products:
    filtered_products = filtered_products[
        filtered_products["brand"].astype(str).isin(selected_brands)
    ]

st.markdown('<p class="eyebrow">Aislewise · Product intelligence</p>', unsafe_allow_html=True)
st.title("See the catalog from every angle.")
manifest = analytics_data["manifest"]
st.caption(
    f"Dataset: {manifest['dataset_version']} · "
    f"{manifest['product_rows']:,} products · "
    f"{manifest['source_table_rows']['retail_traffic.fact_glance_views']:,} traffic events · "
    f"{manifest['source_table_rows']['retail_sales.fact_orders']:,} orders · "
    f"{manifest['observed_rows_across_extracted_tables']:,} source records across ten tables. "
    f"Extracted {manifest['extracted_at_utc']}. Traffic counts are events, not unique visitors."
)

if filtered_products.empty:
    st.info("No products match these filters. Adjust the sidebar to see more of the catalog.")
    st.stop()

stars_count = int((filtered_products["segment"] == "Stars (High Traffic, High Rating)").sum())
at_risk_count = int((filtered_products["segment"] == "At Risk (High Traffic, Low Rating)").sum())
zero_views_count = int(filtered_products["total_views"].eq(0).sum())

metric_columns = st.columns(4)
metric_columns[0].metric("Products in view", format_number(len(filtered_products)))
metric_columns[1].metric("Stars", format_number(stars_count))
metric_columns[2].metric("At risk", format_number(at_risk_count))
metric_columns[3].metric("Zero recorded view events", format_number(zero_views_count))

(
    overview_tab,
    products_tab,
    evidence_tab,
    customers_tab,
    sales_tab,
    traffic_tab,
    inventory_tab,
    reviews_tab,
    fulfillment_tab,
    quality_tab,
) = st.tabs(
    [
        "Executive overview",
        "Product intelligence",
        "Saved visual reports",
        "Customer intelligence",
        "Sales analytics",
        "Traffic analytics",
        "Inventory",
        "Reviews & ratings",
        "Fulfillment",
        "Data quality",
    ]
)

with overview_tab:
    st.subheader("Executive snapshot")
    overview_metrics = st.columns(3)
    overview_metrics[0].metric(
        "Units sold in filtered catalog",
        format_number(int(pd.to_numeric(filtered_products["units_sold"]).sum())),
    )
    overview_metrics[1].metric(
        "Item-line net revenue (source units)",
        f"{pd.to_numeric(filtered_products['item_line_net_revenue']).sum():,.2f}",
    )
    overview_metrics[2].metric(
        "Latest on-hand units",
        format_number(
            int(pd.to_numeric(filtered_products["latest_inventory_units"]).sum())
        ),
    )
    st.caption(
        "These catalog totals use the product filters and cover the full snapshot, not the "
        "selected date range. Item-line net revenue is not profit; the source currency is unknown."
    )
    st.subheader("Portfolio map")
    st.caption("Each dot is a product. Dashed lines mark the shared rating and traffic gates.")
    render_segment_chart(filtered_products)
    st.subheader("Distributions")
    render_distribution_charts(filtered_products)
    st.subheader("Relationships")
    st.caption("Price is shown in source-dataset units; correlation is descriptive, not causal.")
    render_relationship_charts(filtered_products)

with products_tab:
    st.subheader("Filtered products")
    display_columns = [
        "asin",
        "product_title",
        "segment",
        "average_rating",
        "total_views",
        "standard_price",
    ]
    st.dataframe(
        filtered_products[display_columns]
        .sort_values(["total_views", "average_rating"], ascending=[False, False])
        .rename(
            columns={
                "asin": "ASIN",
                "product_title": "Product",
                "segment": "Segment",
                "average_rating": "Rating",
                "total_views": "Recorded views",
                "standard_price": "Listed price (dataset units)",
            }
        ),
        width="stretch",
        hide_index=True,
    )
    download = filtered_products[display_columns].to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download filtered products as CSV",
        data=download,
        file_name="aislewise_filtered_products.csv",
        mime="text/csv",
    )

with evidence_tab:
    st.subheader("Generated visual reports")
    st.caption("Charts are generated directly from the Aislewise analytics dataset.")
    report_images = [
        ("Product portfolio segments", "product_segments.png"),
        ("Category performance", "category_performance.png"),
        ("Brand performance", "brand_performance.png"),
        ("Sales trend", "sales_trend.png"),
        ("Traffic trend", "traffic_trend.png"),
        ("Inventory by fulfillment center", "inventory_by_center.png"),
        ("Review ratings", "review_ratings.png"),
        ("Units by discount band", "discount_units.png"),
    ]
    analytics_visual_dir = VISUALS_PATH / "analytics"
    for index in range(0, len(report_images), 2):
        image_columns = st.columns(2)
        for column, (title, filename) in zip(image_columns, report_images[index : index + 2]):
            image_path = analytics_visual_dir / filename
            with column:
                st.markdown(f"**{title}**")
                if image_path.is_file():
                    st.image(str(image_path), width="stretch")
                else:
                    st.info(f"Run `python eda/visualisations/analytics.py` to generate {filename}.")

with customers_tab:
    st.subheader("Customer purchase behavior by segment")
    if analytics_data is None:
        st.info("Customer-level aggregates are available in the analytics snapshot.")
    else:
        customer_data = analytics_data["customer_segments"]
        if selected_customer_segments:
            customer_data = customer_data[
                customer_data["customer_segment"].astype(str).isin(
                    selected_customer_segments
                )
            ]
        customer_data = customer_data.copy()
        customer_data["customer_count"] = pd.to_numeric(
            customer_data["customer_count"], errors="raise"
        )
        customer_data["purchasers"] = pd.to_numeric(
            customer_data["purchasers"], errors="raise"
        )
        customer_data["repeat_purchasers"] = pd.to_numeric(
            customer_data["repeat_purchasers"], errors="raise"
        )
        metric_columns = st.columns(3)
        metric_columns[0].metric(
            "Customers in segments",
            format_number(int(customer_data["customer_count"].sum())),
        )
        metric_columns[1].metric(
            "Customers with non-cancelled orders",
            format_number(int(customer_data["purchasers"].sum())),
        )
        metric_columns[2].metric(
            "Repeat purchasers (2+ orders)",
            format_number(int(customer_data["repeat_purchasers"].sum())),
        )
        st.bar_chart(
            customer_data.set_index("customer_segment")[
                ["customer_count", "purchasers", "repeat_purchasers"]
            ]
        )
        st.caption(
            "Repeat purchaser means at least two non-cancelled orders in this snapshot. "
            "The dashboard only receives grouped counts; no customer IDs or contact data are exported."
        )
        st.dataframe(customer_data, hide_index=True, width="stretch")

with sales_tab:
    st.subheader("Sales and orders")
    if analytics_data is None:
        st.info("Order and sales aggregates are available in the analytics snapshot.")
    else:
        order_data = analytics_data["orders_daily"].copy()
        order_data["order_date"] = pd.to_datetime(order_data["order_date"])
        date_range = normalize_date_range(selected_date_range)
        if date_range:
            order_data = filter_dates(order_data, "order_date", date_range)
        if not order_data.empty:
            for column in (
                "order_count",
                "units_ordered",
                "order_total_amount",
                "item_line_net_revenue",
            ):
                order_data[column] = pd.to_numeric(order_data[column], errors="coerce").fillna(0)
            metric_columns = st.columns(3)
            metric_columns[0].metric(
                "Orders",
                format_number(int(order_data["order_count"].sum())),
            )
            metric_columns[1].metric(
                "Units ordered",
                format_number(int(order_data["units_ordered"].sum())),
            )
            metric_columns[2].metric(
                "Item-line net revenue (source units)",
                f"{order_data['item_line_net_revenue'].sum():,.2f}",
            )
            st.line_chart(
                order_data.groupby("order_date")[["item_line_net_revenue"]].sum()
            )
            st.caption(
                "Item-line net revenue is the source `net_revenue` sum; it is not profit. "
                "`order_total_amount` is reported separately because it does not reconcile "
                "to item lines for every order. Daily sales are catalog-wide because the "
                "snapshot does not retain a date-by-product sales breakdown."
            )
            st.dataframe(
                order_data.sort_values("order_date", ascending=False),
                hide_index=True,
                width="stretch",
            )
        else:
            st.info("No orders fall within the selected date range.")

with traffic_tab:
    st.subheader("Recorded product traffic")
    if analytics_data is None:
        st.info("Traffic event aggregates are available in the analytics snapshot.")
    else:
        traffic_data = analytics_data["traffic_daily"].copy()
        traffic_data["traffic_date"] = pd.to_datetime(traffic_data["traffic_date"])
        date_range = normalize_date_range(selected_date_range)
        if date_range:
            traffic_data = filter_dates(traffic_data, "traffic_date", date_range)
        selected_asins = set(filtered_products["asin"].astype(str))
        traffic_data = traffic_data[traffic_data["asin"].astype(str).isin(selected_asins)]
        if not traffic_data.empty:
            traffic_data["view_events"] = pd.to_numeric(
                traffic_data["view_events"], errors="raise"
            )
            metric_columns = st.columns(2)
            metric_columns[0].metric(
                "Recorded view events",
                format_number(int(traffic_data["view_events"].sum())),
            )
            metric_columns[1].metric(
                "Products with recorded events",
                format_number(traffic_data["asin"].nunique()),
            )
            st.line_chart(
                traffic_data.groupby("traffic_date")[["view_events"]].sum()
            )
            st.caption(
                "A row is a recorded event, not a unique visitor. The source does not establish "
                "a visitor population aligned to orders, so no conversion rate is calculated."
            )
            st.dataframe(
                traffic_data.groupby("asin", as_index=False)["view_events"]
                .sum()
                .sort_values("view_events", ascending=False)
                .head(100),
                hide_index=True,
                width="stretch",
            )
        else:
            st.info("No traffic events match the active product and date filters.")

with inventory_tab:
    st.subheader("Inventory and stockout monitoring")
    if analytics_data is None:
        st.info("Inventory aggregates are available in the analytics snapshot.")
    else:
        inventory_data = filtered_products.copy()
        inventory_data["latest_inventory_units"] = pd.to_numeric(
            inventory_data["latest_inventory_units"], errors="coerce"
        ).fillna(0)
        stockouts = inventory_data["latest_inventory_units"].eq(0)
        metric_columns = st.columns(3)
        metric_columns[0].metric(
            "Latest on-hand units",
            format_number(int(inventory_data["latest_inventory_units"].sum())),
        )
        metric_columns[1].metric("Products stocked out", format_number(int(stockouts.sum())))
        metric_columns[2].metric(
            "Products represented",
            format_number(len(inventory_data)),
        )
        centers = analytics_data["inventory_by_center"].sort_values(
            "units_in_stock", ascending=False
        )
        st.bar_chart(centers.set_index("fc_name")[["units_in_stock"]])
        st.dataframe(centers, hide_index=True, width="stretch")
        st.caption(
            "Stock is summed across fulfillment centers at each product's latest available "
            "inventory snapshot, which may have different dates by product."
        )

with reviews_tab:
    st.subheader("Ratings and review coverage")
    if analytics_data is None:
        st.info("Review aggregates are available in the analytics snapshot.")
    else:
        st.warning(
            "Review records are synthetic demo data. Reviewer identities and review text are "
            "excluded from this dashboard and published dataset."
        )
        rating_data = analytics_data["review_rating_distribution"]
        st.bar_chart(rating_data, x="review_rating", y="review_count")
        review_products = filtered_products.loc[
            filtered_products["review_count"].gt(0),
            [
                "asin",
                "product_title",
                "average_rating",
                "review_count",
                "average_review_rating",
            ],
        ].sort_values("review_count", ascending=False)
        st.dataframe(review_products.head(100), hide_index=True, width="stretch")

with fulfillment_tab:
    st.subheader("Fulfillment center inventory footprint")
    if analytics_data is None:
        st.info("Fulfillment inventory aggregates are available in the analytics snapshot.")
    else:
        centers = analytics_data["inventory_by_center"].copy()
        if not centers.empty:
            centers["stockout_product_locations"] = pd.to_numeric(
                centers["stockout_product_locations"], errors="coerce"
            ).fillna(0)
            st.bar_chart(
                centers.set_index("fc_name")[["stockout_product_locations"]]
            )
            st.dataframe(centers, hide_index=True, width="stretch")
        st.caption(
            "Fulfillment data describes inventory snapshots by center. Orders do not contain a "
            "verified fulfillment-center key, so order performance is not attributed to centers."
        )

with quality_tab:
    st.subheader("Dataset quality and extraction manifest")
    if analytics_data is None:
        st.info("The quality report is available with the analytics snapshot.")
    else:
        quality = analytics_data["quality"]
        checks = pd.DataFrame(
            [
                {"check": check_name, "rows": count}
                for check_name, count in quality["checks"].items()
            ]
        )
        st.dataframe(checks, hide_index=True, width="stretch")
        mismatch_count = quality["checks"].get(
            "orders_total_vs_item_line_mismatches", 0
        )
        if mismatch_count:
            st.warning(
                f"{mismatch_count:,} orders differ by more than "
                "0.02 source units between the order total "
                "and summed item-line net revenue. This is a reconciliation finding, not "
                "automatically a data error; the amount definitions need confirmation."
            )
        st.json(analytics_data["manifest"])

st.divider()
st.caption(
    "Aislewise is an independent portfolio demo. Sample data is not live or representative of actual "
    "customer behavior; generated review data is synthetic. No profit, unique-visitor count, or "
    "conversion rate is inferred from incompatible or missing source populations."
)
