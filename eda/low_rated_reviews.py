"""Summarize review ratings without exposing individual review content."""

from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = PROJECT_ROOT / "data" / "processed" / "review_rating_distribution.csv"


def main() -> None:
    distribution = pd.read_csv(CSV_PATH)
    if not {"review_rating", "review_count"}.issubset(distribution.columns):
        raise ValueError("Review summary must contain review_rating and review_count.")
    if distribution.empty or distribution["review_count"].sum() <= 0:
        raise ValueError("Review summary contains no rating records.")

    total = int(distribution["review_count"].sum())
    low_count = int(
        distribution.loc[distribution["review_rating"].le(2), "review_count"].sum()
    )
    print("Aggregate synthetic/sample review-rating distribution:")
    print(distribution.to_string(index=False))
    print(f"\nTotal review records: {total:,}")
    print(f"1-2 star records: {low_count:,} ({low_count / total:.1%})")
    print("Reviewer names, identifiers, and review text are not included.")


if __name__ == "__main__":
    main()
