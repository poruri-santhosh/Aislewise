"""Summarize quality characteristics of the expanded product snapshot."""

import pandas as pd

from data_loader import load_data


def main() -> None:
    data = load_data()
    required = ["asin", "product_title", "total_views", "average_rating", "standard_price"]
    missing_columns = set(required).difference(data.columns)
    if missing_columns:
        raise ValueError(f"Expanded product data is missing columns: {sorted(missing_columns)}")

    print("EXPANDED PRODUCT DATA QUALITY")
    print(f"Rows: {len(data):,}")
    print(f"Columns: {len(data.columns):,}")
    print("\nMissing values by column:")
    print(data.isna().sum().sort_values(ascending=False).to_string())
    print(f"\nDuplicate rows: {int(data.duplicated().sum()):,}")
    print(f"Duplicate product keys: {int(data['asin'].duplicated().sum()):,}")
    print(f"Negative traffic event counts: {int(data['total_views'].lt(0).sum()):,}")
    print(f"Negative prices: {int(data['standard_price'].lt(0).sum()):,}")
    print(f"Invalid product ratings: {int((~data['average_rating'].between(0, 5)).sum()):,}")
    zero_events = data[data["total_views"].eq(0)]
    print(f"\nProducts with no recorded view events: {len(zero_events):,}")
    if not zero_events.empty:
        print(zero_events[["asin", "product_title"]].head(10).to_string(index=False))
    print("\nDescriptive statistics:")
    print(data[["total_views", "average_rating", "standard_price"]].describe().round(2))


if __name__ == "__main__":
    main()
