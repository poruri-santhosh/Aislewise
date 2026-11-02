"""Refresh the read-only analytics snapshot from PostgreSQL."""

from analytics_pipeline import build_analytics_snapshot


if __name__ == "__main__":
    manifest = build_analytics_snapshot()
    print(
        "Aislewise analytics snapshot refreshed. "
        f"Products: {manifest['product_rows']:,}; "
        f"source records: {manifest['observed_rows_across_extracted_tables']:,}."
    )
