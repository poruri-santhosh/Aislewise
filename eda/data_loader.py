
from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = PROJECT_ROOT / "data" / "analytics" / "product_performance.csv"


def load_data():
    """Load product-level analytics with the shared EDA column aliases."""
    data = pd.read_csv(DATA_PATH)
    required = {
        "asin",
        "product_title",
        "traffic_event_count",
        "rating",
        "standard_price",
    }
    missing = required.difference(data.columns)
    if missing:
        raise ValueError(f"Product analytics is missing columns: {', '.join(sorted(missing))}")
    return data.rename(
        columns={
            "traffic_event_count": "total_views",
            "rating": "average_rating",
        }
    )


if __name__ == "__main__":
    df = load_data()

    print("Aislewise product analytics loaded successfully!")
    print(f"Rows: {df.shape[0]}")
    print(f"Columns: {df.shape[1]}")
    print(df.head())
