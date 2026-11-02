import os
import sys
from pathlib import Path

sys.path.append(
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..")
    )
)
import pandas as pd
from data_loader import load_data
from portfolio import classify_product

df = load_data()

# 1. Segment the products using the shared, tested business thresholds.
df["segment"] = df.apply(
    lambda row: classify_product(row["total_views"], row["average_rating"]),
    axis=1,
)

# 2. Print Segment Counts
print("=" * 65)
print("AMAZON PRODUCT SEGMENT COUNTS:")
print(df["segment"].value_counts())
print("=" * 65)

# 3. Focus on "Hidden Gems" (Top Priority for Marketing Team)
hidden_gems = df[
    df["segment"] == "Hidden Gems (Low Traffic, High Rating)"
].sort_values(by="average_rating", ascending=False)

print(f"\nTOTAL HIDDEN GEMS FOUND: {len(hidden_gems)}")
print("\nTOP 5 HIDDEN GEMS TO PROMOTE:")
print(
    hidden_gems[
        [
            "asin",
            "product_title",
            "average_rating",
            "standard_price",
            "total_views",
        ]
    ].head()
)

# 4. Focus on "Stars" (Top Performing Hero Products)
stars = df[df["segment"] == "Stars (High Traffic, High Rating)"].sort_values(
    by="total_views", ascending=False
)
print(f"\nTOTAL STARS (HERO PRODUCTS) FOUND: {len(stars)}")
print("\nTOP 5 HERO PRODUCTS:")
print(
    stars[
        [
            "asin",
            "product_title",
            "average_rating",
            "standard_price",
            "total_views",
        ]
    ].head()
)

# 5. Export results to CSV for stakeholders/dashboard
output_path = os.path.join(
    str(Path(__file__).resolve().parents[1]),
    "data",
    "processed",
    "product_segmentation_recommendations.csv",
)
os.makedirs(os.path.dirname(output_path), exist_ok=True)
df.to_csv(output_path, index=False)
print(f"\n[SUCCESS] Full segmented dataset exported to: {output_path}")