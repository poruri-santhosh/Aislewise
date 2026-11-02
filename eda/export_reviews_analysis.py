"""Export an aggregate rating distribution without reviewer identifiers or text."""

from pathlib import Path

import pandas as pd

from app import database_connection

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = PROJECT_ROOT / "data" / "processed" / "review_rating_distribution.csv"
QUERY = """
    SELECT rating AS review_rating, COUNT(*) AS review_count
    FROM catalog.dim_reviews
    GROUP BY rating
    ORDER BY rating
"""


def export_review_rating_distribution() -> int:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with database_connection() as connection:
        connection.set_session(readonly=True)
        distribution = pd.read_sql_query(QUERY, connection)

    distribution.to_csv(OUTPUT_PATH, index=False)
    return int(distribution["review_count"].sum())


if __name__ == "__main__":
    total_reviews = export_review_rating_distribution()
    print(f"Exported aggregate counts for {total_reviews:,} reviews without review text or IDs.")
