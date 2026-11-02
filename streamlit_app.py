"""Aislewise's interactive, snapshot-based retail analytics dashboard."""

from pathlib import Path
import sys

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_PATH = PROJECT_ROOT / "data" / "raw" / "product_views_analysis.csv"
REVIEW_PATH = PROJECT_ROOT / "data" / "processed" / "at_risk_products_reviews.csv"
VISUALS_PATH = PROJECT_ROOT / "reports" / "visualisations"
EDA_PATH = PROJECT_ROOT / "eda"
if str(EDA_PATH) not in sys.path:
    sys.path.insert(0, str(EDA_PATH))

from portfolio import HIGH_RATING, HIGH_TRAFFIC_VIEWS, classify_product

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


@st.cache_data
def load_products(path: str, modified_time: float) -> pd.DataFrame:
    """Load and validate the bundled product snapshot."""
    del modified_time
    data = pd.read_csv(path)
    required = {
        "asin",
        "product_title",
        "total_views",
        "average_rating",
        "standard_price",
    }
    missing = required.difference(data.columns)
    if missing:
        raise ValueError(f"Product snapshot is missing required columns: {', '.join(sorted(missing))}")

    data = data.copy()
    for column in ("total_views", "average_rating", "standard_price"):
        data[column] = pd.to_numeric(data[column], errors="raise")

    if data.empty:
        raise ValueError("Product snapshot contains no products.")
    if data[list(required)].isnull().any().any():
        raise ValueError("Product snapshot contains missing values in required fields.")
    if (data["total_views"] < 0).any():
        raise ValueError("Product snapshot contains negative view counts.")
    if (data["standard_price"] <= 0).any():
        raise ValueError("Product snapshot contains non-positive prices.")
    if (~data["average_rating"].between(0, 5)).any():
        raise ValueError("Product snapshot contains ratings outside the 0–5 range.")

    data["segment"] = data.apply(
        lambda row: classify_product(row["total_views"], row["average_rating"]),
        axis=1,
    )
    return data


def format_number(value: float) -> str:
    return f"{value:,.0f}"


@st.cache_data
def load_review_sample(path: str, modified_time: float) -> pd.DataFrame:
    del modified_time
    return pd.read_csv(path)


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


try:
    products = load_products(str(DATA_PATH), DATA_PATH.stat().st_mtime)
except (OSError, pd.errors.ParserError, ValueError) as error:
    st.error(f"Could not load the bundled product snapshot: {error}")
    st.stop()

st.markdown('<p class="eyebrow">Aislewise · Product intelligence</p>', unsafe_allow_html=True)
st.title("See the catalog from every angle.")
st.caption(
    "An interactive view of the bundled 79-product analytics sample. "
    "This dashboard is a snapshot—not live inventory, sales, or verified customer behavior."
)

with st.sidebar:
    st.header("Explore the snapshot")
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
        "Listed price range (dataset units)",
        min_value=price_bounds[0],
        max_value=price_bounds[1],
        value=price_bounds,
    )
    view_bounds = (int(products["total_views"].min()), int(products["total_views"].max()))
    selected_views = st.slider(
        "Recorded view range",
        min_value=view_bounds[0],
        max_value=view_bounds[1],
        value=view_bounds,
    )
    st.divider()
    st.caption("Segment gates: rating ≥ 4.2 and views ≥ 20.")

filtered_products = apply_filters(
    products,
    search_query.strip(),
    selected_segments,
    minimum_rating,
    selected_prices,
    selected_views,
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
metric_columns[3].metric("Zero recorded views", format_number(zero_views_count))

overview_tab, products_tab, evidence_tab = st.tabs(
    ["Portfolio overview", "Product explorer", "Saved visual reports"]
)

with overview_tab:
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
    st.caption("These are the committed PNG outputs from the offline analytics workflow.")
    report_images = [
        ("Portfolio segmentation", "SEGMENTATION.png"),
        ("Product views distribution", "product_views_distribution.png"),
        ("Product views boxplot", "product_views_boxplot.png"),
        ("Price vs. product views", "product_price_vs_views.png"),
        ("Product metric correlation", "product_metrics_correlation.png"),
    ]
    for index in range(0, len(report_images), 2):
        image_columns = st.columns(2)
        for column, (title, filename) in zip(image_columns, report_images[index : index + 2]):
            image_path = VISUALS_PATH / filename
            with column:
                st.markdown(f"**{title}**")
                if image_path.is_file():
                    st.image(str(image_path), width="stretch")
                else:
                    st.warning(f"Saved chart is not present in this deployment: {filename}")

    if REVIEW_PATH.is_file():
        st.divider()
        st.subheader("Review sample audit")
        st.warning(
            "This review extract contains synthetic demo text and ratings. "
            "It is for validating the analytics workflow only—not evidence of real customer sentiment."
        )
        try:
            review_sample = load_review_sample(str(REVIEW_PATH), REVIEW_PATH.stat().st_mtime)
            st.metric("Synthetic review rows in sample", format_number(len(review_sample)))
            if "individual_review_rating" in review_sample.columns:
                review_counts = (
                    review_sample["individual_review_rating"]
                    .value_counts()
                    .sort_index()
                    .rename_axis("Synthetic rating")
                    .reset_index(name="Review rows")
                )
                st.bar_chart(review_counts, x="Synthetic rating", y="Review rows")
            st.dataframe(review_sample.head(20), width="stretch", hide_index=True)
        except (OSError, pd.errors.ParserError, ValueError) as error:
            st.error(f"Could not load the synthetic review sample: {error}")

st.divider()
st.caption(
    "Aislewise is an independent portfolio demo. Sample data is not live or representative of actual "
    "customer behavior; review data is synthetic. Product ratings and traffic should be validated "
    "against aligned, authorized production sources before business decisions."
)
