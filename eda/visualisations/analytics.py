"""Generate charts from the sanitized Aislewise analytics dataset."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = PROJECT_ROOT / "data" / "analytics"
OUTPUT_PATH = PROJECT_ROOT / "reports" / "visualisations" / "analytics"

sns.set_theme(style="whitegrid", palette="deep")


def _read_csv(name: str, required: set[str]) -> pd.DataFrame:
    data = pd.read_csv(DATA_PATH / name)
    missing = required.difference(data.columns)
    if missing:
        raise ValueError(f"{name} is missing required columns: {', '.join(sorted(missing))}")
    if data.empty:
        raise ValueError(f"{name} has no rows; refusing to generate an empty chart.")
    return data


def _save(fig: plt.Figure, filename: str) -> None:
    OUTPUT_PATH.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(OUTPUT_PATH / filename, dpi=160, bbox_inches="tight")
    plt.close(fig)


def generate_visualizations() -> list[Path]:
    OUTPUT_PATH.mkdir(parents=True, exist_ok=True)
    created = []

    products = _read_csv(
        "product_performance.csv",
        {"segment", "category", "brand", "rating", "traffic_event_count"},
    )
    segments = (
        products["segment"]
        .value_counts()
        .rename_axis("segment")
        .reset_index(name="products")
        .sort_values("products")
    )
    fig, axis = plt.subplots(figsize=(10, 5))
    sns.barplot(data=segments, x="products", y="segment", ax=axis, color="#16856b")
    axis.set(title=f"Aislewise product portfolio ({len(products):,} products)", xlabel="Products", ylabel="")
    target = OUTPUT_PATH / "product_segments.png"
    _save(fig, target.name)
    created.append(target)

    categories = _read_csv(
        "category_performance.csv",
        {"category", "item_line_net_revenue", "product_count"},
    ).nlargest(15, "item_line_net_revenue")
    fig, axis = plt.subplots(figsize=(11, 6))
    sns.barplot(
        data=categories,
        x="item_line_net_revenue",
        y="category",
        hue="department",
        dodge=False,
        ax=axis,
    )
    axis.set(
        title="Category item-line net revenue (top 15)",
        xlabel="Source item-line net revenue",
        ylabel="Category",
    )
    axis.legend(title="Department", bbox_to_anchor=(1.02, 1), loc="upper left")
    target = OUTPUT_PATH / "category_performance.png"
    _save(fig, target.name)
    created.append(target)

    brands = _read_csv(
        "brand_performance.csv",
        {"brand", "item_line_net_revenue", "product_count"},
    ).nlargest(15, "item_line_net_revenue")
    fig, axis = plt.subplots(figsize=(11, 6))
    sns.barplot(data=brands, x="item_line_net_revenue", y="brand", ax=axis, color="#4278c5")
    axis.set(title="Brand item-line net revenue (top 15)", xlabel="Source item-line net revenue", ylabel="Brand")
    target = OUTPUT_PATH / "brand_performance.png"
    _save(fig, target.name)
    created.append(target)

    orders = _read_csv(
        "orders_daily.csv",
        {"order_date", "order_count", "item_line_net_revenue"},
    )
    orders["order_date"] = pd.to_datetime(orders["order_date"], errors="raise")
    sales_by_day = orders.groupby("order_date", as_index=False)["item_line_net_revenue"].sum()
    fig, axis = plt.subplots(figsize=(12, 5))
    sns.lineplot(data=sales_by_day, x="order_date", y="item_line_net_revenue", ax=axis)
    axis.set(
        title="Daily item-line net revenue",
        xlabel="Order date",
        ylabel="Source item-line net revenue",
    )
    target = OUTPUT_PATH / "sales_trend.png"
    _save(fig, target.name)
    created.append(target)

    traffic = _read_csv("traffic_daily.csv", {"traffic_date", "view_events"})
    traffic["traffic_date"] = pd.to_datetime(traffic["traffic_date"], errors="raise")
    traffic_by_day = traffic.groupby("traffic_date", as_index=False)["view_events"].sum()
    fig, axis = plt.subplots(figsize=(12, 5))
    sns.lineplot(data=traffic_by_day, x="traffic_date", y="view_events", ax=axis)
    axis.set(title="Daily recorded traffic events", xlabel="Event date", ylabel="View events (not unique visitors)")
    target = OUTPUT_PATH / "traffic_trend.png"
    _save(fig, target.name)
    created.append(target)

    inventory = _read_csv(
        "inventory_by_center.csv",
        {"fc_name", "units_in_stock", "stockout_product_locations"},
    ).sort_values("units_in_stock", ascending=False)
    fig, axis = plt.subplots(figsize=(11, 6))
    sns.barplot(data=inventory, x="units_in_stock", y="fc_name", ax=axis, color="#d58a27")
    axis.set(title="Latest inventory snapshot by fulfillment center", xlabel="On-hand units", ylabel="Center")
    target = OUTPUT_PATH / "inventory_by_center.png"
    _save(fig, target.name)
    created.append(target)

    ratings = _read_csv("review_rating_distribution.csv", {"review_rating", "review_count"})
    fig, axis = plt.subplots(figsize=(8, 5))
    sns.barplot(data=ratings, x="review_rating", y="review_count", ax=axis, color="#7357a5")
    axis.set(title="Synthetic review rating distribution", xlabel="Rating (1–5)", ylabel="Review records")
    target = OUTPUT_PATH / "review_ratings.png"
    _save(fig, target.name)
    created.append(target)

    discount = _read_csv(
        "discount_effectiveness.csv",
        {"discount_band", "product_count", "units_sold", "item_line_net_revenue"},
    )
    fig, axis = plt.subplots(figsize=(10, 5))
    sns.barplot(data=discount, x="discount_band", y="units_sold", ax=axis, color="#16856b")
    axis.set(
        title="Observed units sold by discount band (descriptive)",
        xlabel="Catalog discount band",
        ylabel="Units sold",
    )
    target = OUTPUT_PATH / "discount_units.png"
    _save(fig, target.name)
    created.append(target)

    return created


if __name__ == "__main__":
    for chart in generate_visualizations():
        print(f"Generated {chart.relative_to(PROJECT_ROOT)}")
