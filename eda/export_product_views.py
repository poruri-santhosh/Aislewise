"""Compatibility entry point for the read-only, baseline-preserving pipeline."""

from expanded_pipeline import build_expanded_snapshot


if __name__ == "__main__":
    manifest = build_expanded_snapshot()
    print(
        "Expanded analytics snapshot refreshed; baseline remains unchanged. "
        f"Products: {manifest['expanded_product_rows']:,}; "
        f"new products vs baseline: {manifest['new_products_vs_baseline']:,}."
    )
