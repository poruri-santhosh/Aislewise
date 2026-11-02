import csv
import sys
import unittest
from collections import Counter
from pathlib import Path

from streamlit.testing.v1 import AppTest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "eda"))

from portfolio import classify_product


DATA_PATH = PROJECT_ROOT / "data" / "raw" / "product_views_analysis.csv"
EXPECTED_SEGMENT_COUNTS = {
    "Stars (High Traffic, High Rating)": 35,
    "Hidden Gems (Low Traffic, High Rating)": 17,
    "At Risk (High Traffic, Low Rating)": 27,
    "Dead Weight (Low Traffic, Low Rating)": 0,
}


def load_snapshot():
    with DATA_PATH.open(newline="", encoding="utf-8-sig") as source:
        return list(csv.DictReader(source))


class AnalyticsSnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.products = load_snapshot()

    def test_snapshot_schema_and_product_count(self):
        self.assertEqual(
            set(self.products[0]),
            {"asin", "product_title", "total_views", "average_rating", "standard_price"},
        )
        self.assertEqual(len(self.products), 79)

    def test_product_ids_are_unique_and_metrics_are_valid(self):
        asins = [product["asin"] for product in self.products]
        self.assertEqual(len(asins), len(set(asins)))
        for product in self.products:
            self.assertGreaterEqual(int(product["total_views"]), 0)
            self.assertGreater(float(product["standard_price"]), 0)
            self.assertTrue(0 <= float(product["average_rating"]) <= 5)

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

    def test_snapshot_segment_counts(self):
        segment_counts = Counter(
            {segment: 0 for segment in EXPECTED_SEGMENT_COUNTS}
        )
        segment_counts.update(
            classify_product(
                int(product["total_views"]),
                float(product["average_rating"]),
            )
            for product in self.products
        )
        self.assertEqual(dict(segment_counts), EXPECTED_SEGMENT_COUNTS)

    def test_zero_view_products_are_not_assumed_to_be_low_quality(self):
        zero_view_products = [
            product
            for product in self.products
            if int(product["total_views"]) == 0
        ]
        self.assertEqual(len(zero_view_products), 15)
        self.assertTrue(
            all(
                classify_product(
                    int(product["total_views"]),
                    float(product["average_rating"]),
                )
                == "Hidden Gems (Low Traffic, High Rating)"
                for product in zero_view_products
            )
        )

    def test_streamlit_dashboard_renders_without_errors(self):
        app = AppTest.from_file(str(PROJECT_ROOT / "streamlit_app.py")).run(timeout=20)
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any("See the catalog from every angle." in title.value for title in app.title))


if __name__ == "__main__":
    unittest.main()
