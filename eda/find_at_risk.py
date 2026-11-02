import os
import sys

sys.path.append(
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..")
    )
)
import pandas as pd
from data_loader import load_data
from portfolio import classify_product

df = load_data()
df["segment"] = df.apply(
    lambda row: classify_product(row["total_views"], row["average_rating"]),
    axis=1,
)

# 2. Filter At Risk products
at_risk_products = df[df["segment"] == "At Risk (High Traffic, Low Rating)"].sort_values(
    by="total_views", ascending=False
)

print("=" * 65)
print(f"TOTAL AT-RISK PRODUCTS FOUND: {len(at_risk_products):,}")
print("=" * 65)
print(
    at_risk_products[
        [
            "asin",
            "product_title",
            "average_rating",
            "standard_price",
            "total_views",
        ]
    ].head(100).to_string(index=False)
)