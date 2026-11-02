import json
import os
import sys
import unittest
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from streamlit.testing.v1 import AppTest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPANDED_PATH = PROJECT_ROOT / "data" / "expanded"
EDA_PATH = PROJECT_ROOT / "eda"
sys.path.insert(0, str(EDA_PATH))
load_dotenv(PROJECT_ROOT / ".env")

from portfolio import classify_product

OWNER_REPORTED_ADDITION_COUNTS = {
    "catalog.dim_products": 8_000,
    "customers.dim_customers": 5_000,
    "fulfillment.dim_fulfillment_centers": 50,
    "retail_traffic.fact_glance_views": 33_000,
    "retail_sales.fact_orders": 7_000,
    "retail_sales.fact_order_items": 14_000,
    "retail_inventory.fact_fba_inventory_daily": 5_000,
    "catalog.dim_reviews": 4_000,
    "customers.cart_items": 2_000,
    "customers.wishlists": 1_950,
}


class ExpandedAnalyticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(
            (EXPANDED_PATH / "manifest.json").read_text(encoding="utf-8")
        )
        cls.quality = json.loads(
            (EXPANDED_PATH / "data_quality.json").read_text(encoding="utf-8")
        )

    def test_expanded_product_snapshot_is_complete_and_unique(self):
        products = pd.read_csv(EXPANDED_PATH / "product_performance.csv")
        recommendations = pd.read_csv(
            EXPANDED_PATH / "product_segmentation_recommendations.csv"
        )
        self.assertEqual(len(products), self.manifest["product_rows"])
        self.assertEqual(products["asin"].nunique(), len(products))
        self.assertGreater(len(products), 8_000)
        self.assertEqual(self.manifest["product_rows"], 8_079)
        self.assertEqual(self.manifest["owner_reported_synthetic_addition_total"], 80_000)
        self.assertEqual(len(recommendations), len(products))
        self.assertEqual(recommendations["asin"].tolist(), products["asin"].tolist())
        self.assertEqual(recommendations["segment"].tolist(), products["segment"].tolist())
        self.assertEqual(
            self.manifest["persisted_output_rows"][
                "product_segmentation_recommendations.csv"
            ],
            len(products),
        )

    def test_owner_reported_record_additions_match_the_release_manifest(self):
        self.assertEqual(
            self.manifest["owner_reported_synthetic_additions"],
            OWNER_REPORTED_ADDITION_COUNTS,
        )
        self.assertEqual(sum(OWNER_REPORTED_ADDITION_COUNTS.values()), 80_000)
        self.assertEqual(
            self.manifest["observed_rows_across_extracted_tables"],
            sum(self.manifest["source_table_rows"].values()),
        )

    def test_aggregated_exports_exclude_personal_identifiers_and_review_text(self):
        prohibited_columns = {
            "customer_id",
            "email",
            "name",
            "password_hash",
            "review_text",
            "review_title",
            "customer_name",
            "order_id",
            "tracking_number",
        }
        for csv_path in EXPANDED_PATH.glob("*.csv"):
            columns = set(pd.read_csv(csv_path, nrows=0).columns)
            self.assertFalse(
                prohibited_columns.intersection(columns),
                f"Sensitive columns found in {csv_path.name}",
            )

    def test_quality_checks_find_no_key_fk_or_range_violations(self):
        failed_checks = {
            name: count
            for name, count in self.quality["checks"].items()
            if count
            and name
            not in {
                "orders_total_vs_item_line_mismatches",
                "inventory_stockout_flag_mismatches",
            }
        }
        self.assertEqual(failed_checks, {})
        self.assertEqual(
            self.quality["checks"]["orders_total_vs_item_line_mismatches"],
            875,
        )
        self.assertEqual(self.quality["checks"]["inventory_stockout_flag_mismatches"], 136)

    def test_daily_aggregates_reconcile_to_source_table_counts(self):
        daily_traffic = pd.read_csv(EXPANDED_PATH / "traffic_daily.csv")
        daily_orders = pd.read_csv(EXPANDED_PATH / "orders_daily.csv")
        review_ratings = pd.read_csv(EXPANDED_PATH / "review_rating_distribution.csv")
        self.assertEqual(
            int(daily_traffic["view_events"].sum()),
            self.manifest["source_table_rows"]["retail_traffic.fact_glance_views"],
        )
        self.assertEqual(
            int(daily_orders["order_count"].sum()),
            self.manifest["source_table_rows"]["retail_sales.fact_orders"],
        )
        self.assertEqual(
            int(review_ratings["review_count"].sum()),
            self.manifest["source_table_rows"]["catalog.dim_reviews"],
        )

    def test_segment_thresholds_are_inclusive(self):
        self.assertEqual(classify_product(20, 4.2), "Stars (High Traffic, High Rating)")
        self.assertEqual(
            classify_product(19, 4.2), "Hidden Gems (Low Traffic, High Rating)"
        )
        self.assertEqual(
            classify_product(20, 4.19), "At Risk (High Traffic, Low Rating)"
        )
        self.assertEqual(
            classify_product(19, 4.19), "Dead Weight (Low Traffic, Low Rating)"
        )

    def test_expanded_visualizations_generate_nonempty_pngs(self):
        from visualisations.expanded import generate_visualizations

        generated = generate_visualizations()
        self.assertEqual(len(generated), 8)
        self.assertTrue(all(path.is_file() and path.stat().st_size > 1_000 for path in generated))

    def test_streamlit_dashboard_renders_with_expanded_dataset(self):
        app = AppTest.from_file(str(PROJECT_ROOT / "streamlit_app.py")).run(timeout=60)
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any("See the catalog from every angle." in title.value for title in app.title))
        self.assertTrue(any("Customer intelligence" in tab.label for tab in app.tabs))
        self.assertTrue(any("Data quality" in tab.label for tab in app.tabs))


@unittest.skipUnless(os.getenv("DATABASE_URL"), "DATABASE_URL is not configured.")
class ReadOnlyDatabaseIntegrationTests(unittest.TestCase):
    def test_database_connectivity_schema_and_catalog_completeness(self):
        from app import database_connection

        with database_connection() as connection:
            connection.set_session(readonly=True)
            with connection.cursor() as cursor:
                cursor.execute("SHOW transaction_read_only")
                self.assertEqual(cursor.fetchone()[0], "on")
                cursor.execute("SELECT COUNT(*) FROM catalog.dim_products")
                self.assertEqual(
                    cursor.fetchone()[0],
                    self.manifest_product_count(),
                )
                cursor.execute(
                    """
                    SELECT COUNT(*)
                    FROM retail_traffic.fact_glance_views v
                    LEFT JOIN catalog.dim_products p ON p.asin = v.asin
                    LEFT JOIN customers.dim_customers c ON c.customer_id = v.customer_id
                    WHERE p.asin IS NULL OR c.customer_id IS NULL
                    """
                )
                self.assertEqual(cursor.fetchone()[0], 0)
            connection.rollback()

    @staticmethod
    def manifest_product_count() -> int:
        manifest_path = EXPANDED_PATH / "manifest.json"
        return int(json.loads(manifest_path.read_text(encoding="utf-8"))["product_rows"])


if __name__ == "__main__":
    unittest.main()
