"""Read-only PostgreSQL extraction and DuckDB analytics for Aislewise."""

from __future__ import annotations

import csv
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import database_connection

OUTPUT_PATH = PROJECT_ROOT / "data" / "analytics"
BATCH_SIZE = 2_000
SOURCE_TABLES = {
    "catalog.dim_products": "products",
    "customers.dim_customers": "customers",
    "fulfillment.dim_fulfillment_centers": "fulfillment_centers",
    "retail_traffic.fact_glance_views": "traffic_events",
    "retail_sales.fact_orders": "orders",
    "retail_sales.fact_order_items": "order_items",
    "retail_inventory.fact_fba_inventory_daily": "inventory_snapshots",
    "catalog.dim_reviews": "reviews",
    "customers.cart_items": "cart_items",
    "customers.wishlists": "wishlists",
}
REQUIRED_COLUMNS = {
    "catalog.dim_products": {
        "asin", "product_title", "brand", "category_id", "standard_price",
        "original_price", "discount_percent", "rating", "rating_count",
    },
    "catalog.dim_categories": {"category_id", "category_name", "department"},
    "customers.dim_customers": {"customer_id", "customer_segment"},
    "fulfillment.dim_fulfillment_centers": {
        "fulfillment_center_id", "fc_name", "city", "state", "country",
    },
    "retail_traffic.fact_glance_views": {
        "view_id", "asin", "customer_id", "view_timestamp",
        "is_buy_box_winner", "estimated_delivery_days",
    },
    "retail_sales.fact_orders": {
        "order_id", "customer_id", "order_timestamp", "payment_method",
        "order_status", "total_amount",
    },
    "retail_sales.fact_order_items": {
        "order_item_id", "order_id", "asin", "ordered_units", "net_revenue",
    },
    "retail_inventory.fact_fba_inventory_daily": {
        "snapshot_date", "asin", "fulfillment_center_id", "units_in_stock",
        "units_reserved", "out_of_stock_flag",
    },
    "catalog.dim_reviews": {"review_id", "asin", "customer_id", "rating"},
    "customers.cart_items": {
        "customer_id", "asin", "quantity", "is_saved_for_later",
    },
    "customers.wishlists": {"customer_id", "asin"},
}
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("aislewise.analytics_pipeline")

EXTRACT_QUERIES = {
    "products.csv": """
        WITH latest_snapshot AS (
            SELECT asin, MAX(snapshot_date) AS snapshot_date
            FROM retail_inventory.fact_fba_inventory_daily
            GROUP BY asin
        ),
        latest_inventory AS (
            SELECT i.asin, s.snapshot_date,
                   SUM(i.units_in_stock) AS units_in_stock,
                   SUM(i.units_reserved) AS units_reserved
            FROM retail_inventory.fact_fba_inventory_daily i
            JOIN latest_snapshot s
              ON s.asin = i.asin AND s.snapshot_date = i.snapshot_date
            GROUP BY i.asin, s.snapshot_date
        )
        SELECT p.asin, p.product_title, p.brand,
               COALESCE(c.category_name, 'Uncategorized') AS category,
               COALESCE(c.department, 'Uncategorized') AS department,
               p.standard_price, p.original_price, p.discount_percent,
               p.rating, p.rating_count, i.snapshot_date AS inventory_snapshot_date,
               COALESCE(i.units_in_stock, 0) AS latest_inventory_units,
               COALESCE(i.units_reserved, 0) AS latest_reserved_units
        FROM catalog.dim_products p
        LEFT JOIN catalog.dim_categories c ON c.category_id = p.category_id
        LEFT JOIN latest_inventory i ON i.asin = p.asin
        ORDER BY p.asin
    """,
    "traffic_daily.csv": """
        SELECT view_timestamp::date AS traffic_date, asin,
               COUNT(*) AS view_events,
               COUNT(*) FILTER (WHERE is_buy_box_winner) AS buy_box_winning_view_events,
               AVG(estimated_delivery_days)::numeric(10, 2) AS avg_estimated_delivery_days
        FROM retail_traffic.fact_glance_views
        GROUP BY view_timestamp::date, asin
        ORDER BY traffic_date, asin
    """,
    "orders_daily.csv": """
        WITH line_totals AS (
            SELECT order_id, COUNT(*) AS order_line_count,
                   SUM(ordered_units) AS units_ordered,
                   SUM(net_revenue) AS line_net_revenue
            FROM retail_sales.fact_order_items
            GROUP BY order_id
        )
        SELECT o.order_timestamp::date AS order_date, o.order_status,
               o.payment_method, COUNT(*) AS order_count,
               SUM(COALESCE(l.order_line_count, 0)) AS order_line_count,
               SUM(COALESCE(l.units_ordered, 0)) AS units_ordered,
               SUM(COALESCE(o.total_amount, 0)) AS order_total_amount,
               SUM(COALESCE(l.line_net_revenue, 0)) AS item_line_net_revenue
        FROM retail_sales.fact_orders o
        LEFT JOIN line_totals l ON l.order_id = o.order_id
        GROUP BY o.order_timestamp::date, o.order_status, o.payment_method
        ORDER BY order_date, o.order_status, o.payment_method
    """,
    "product_sales.csv": """
        SELECT asin, COUNT(*) AS order_line_count,
               SUM(ordered_units) AS units_sold,
               SUM(net_revenue) AS item_line_net_revenue
        FROM retail_sales.fact_order_items
        GROUP BY asin
        ORDER BY asin
    """,
    "customer_segments.csv": """
        WITH customer_orders AS (
            SELECT customer_id,
                   COUNT(*) FILTER (
                       WHERE LOWER(COALESCE(order_status, '')) NOT IN ('cancelled', 'canceled')
                   ) AS non_cancelled_order_count,
                   SUM(total_amount) FILTER (
                       WHERE LOWER(COALESCE(order_status, '')) NOT IN ('cancelled', 'canceled')
                   ) AS non_cancelled_order_total
            FROM retail_sales.fact_orders
            GROUP BY customer_id
        )
        SELECT COALESCE(NULLIF(c.customer_segment, ''), 'Unspecified') AS customer_segment,
               COUNT(*) AS customer_count,
               COUNT(*) FILTER (WHERE COALESCE(o.non_cancelled_order_count, 0) > 0) AS purchasers,
               COUNT(*) FILTER (WHERE COALESCE(o.non_cancelled_order_count, 0) >= 2) AS repeat_purchasers,
               SUM(COALESCE(o.non_cancelled_order_count, 0)) AS non_cancelled_orders,
               SUM(COALESCE(o.non_cancelled_order_total, 0)) AS order_total_amount
        FROM customers.dim_customers c
        LEFT JOIN customer_orders o ON o.customer_id = c.customer_id
        GROUP BY COALESCE(NULLIF(c.customer_segment, ''), 'Unspecified')
        ORDER BY customer_segment
    """,
    "inventory_by_center.csv": """
        WITH latest_snapshot AS (
            SELECT asin, MAX(snapshot_date) AS snapshot_date
            FROM retail_inventory.fact_fba_inventory_daily
            GROUP BY asin
        )
        SELECT MIN(i.snapshot_date) AS earliest_snapshot_date,
               MAX(i.snapshot_date) AS latest_snapshot_date,
               i.fulfillment_center_id, f.fc_name,
               f.city, f.state, f.country,
               COUNT(DISTINCT i.asin) AS product_locations,
               SUM(i.units_in_stock) AS units_in_stock,
               SUM(i.units_reserved) AS units_reserved,
               COUNT(DISTINCT i.asin) FILTER (WHERE i.units_in_stock = 0) AS stockout_product_locations,
               COUNT(*) FILTER (
                   WHERE i.out_of_stock_flag IS DISTINCT FROM (i.units_in_stock = 0)
               ) AS stockout_flag_mismatches
        FROM retail_inventory.fact_fba_inventory_daily i
        JOIN latest_snapshot s ON s.asin = i.asin AND s.snapshot_date = i.snapshot_date
        JOIN fulfillment.dim_fulfillment_centers f
          ON f.fulfillment_center_id = i.fulfillment_center_id
        GROUP BY i.fulfillment_center_id, f.fc_name, f.city, f.state, f.country
        ORDER BY i.fulfillment_center_id
    """,
    "reviews_by_product.csv": """
        SELECT asin, COUNT(*) AS review_count,
               AVG(rating)::numeric(10, 2) AS average_review_rating,
               COUNT(*) FILTER (WHERE rating <= 2) AS low_rating_review_count,
               COUNT(*) FILTER (WHERE rating >= 4) AS high_rating_review_count
        FROM catalog.dim_reviews
        GROUP BY asin
        ORDER BY asin
    """,
    "review_rating_distribution.csv": """
        SELECT rating AS review_rating, COUNT(*) AS review_count
        FROM catalog.dim_reviews
        GROUP BY rating
        ORDER BY rating
    """,
    "shopping_intent_by_product.csv": """
        WITH cart AS (
            SELECT asin,
                   COUNT(*) FILTER (WHERE NOT is_saved_for_later) AS active_cart_lines,
                   SUM(quantity) FILTER (WHERE NOT is_saved_for_later) AS active_cart_units,
                   COUNT(*) FILTER (WHERE is_saved_for_later) AS saved_cart_lines
            FROM customers.cart_items
            GROUP BY asin
        ),
        saved AS (
            SELECT asin, COUNT(*) AS wishlist_additions
            FROM customers.wishlists
            GROUP BY asin
        )
        SELECT p.asin, COALESCE(c.active_cart_lines, 0) AS active_cart_lines,
               COALESCE(c.active_cart_units, 0) AS active_cart_units,
               COALESCE(c.saved_cart_lines, 0) AS saved_cart_lines,
               COALESCE(w.wishlist_additions, 0) AS wishlist_additions
        FROM catalog.dim_products p
        LEFT JOIN cart c ON c.asin = p.asin
        LEFT JOIN saved w ON w.asin = p.asin
        ORDER BY p.asin
    """,
}

QUALITY_QUERIES = {
    "duplicate_product_keys": """
        SELECT COUNT(*) FROM (
            SELECT asin FROM catalog.dim_products GROUP BY asin HAVING COUNT(*) > 1
        ) q
    """,
    "required_product_fields_missing": """
        SELECT COUNT(*) FROM catalog.dim_products
        WHERE asin IS NULL OR product_title IS NULL OR brand IS NULL
           OR standard_price IS NULL OR rating IS NULL
    """,
    "invalid_product_discounts_or_ratings": """
        SELECT COUNT(*) FROM catalog.dim_products
        WHERE discount_percent NOT BETWEEN 0 AND 100
           OR rating NOT BETWEEN 0 AND 5 OR rating_count < 0
    """,
    "duplicate_customer_keys": """
        SELECT COUNT(*) FROM (
            SELECT customer_id FROM customers.dim_customers
            GROUP BY customer_id HAVING COUNT(*) > 1
        ) q
    """,
    "duplicate_fulfillment_center_keys": """
        SELECT COUNT(*) FROM (
            SELECT fulfillment_center_id FROM fulfillment.dim_fulfillment_centers
            GROUP BY fulfillment_center_id HAVING COUNT(*) > 1
        ) q
    """,
    "duplicate_traffic_event_keys": """
        SELECT COUNT(*) FROM (
            SELECT view_id FROM retail_traffic.fact_glance_views
            GROUP BY view_id HAVING COUNT(*) > 1
        ) q
    """,
    "duplicate_order_keys": """
        SELECT COUNT(*) FROM (
            SELECT order_id FROM retail_sales.fact_orders
            GROUP BY order_id HAVING COUNT(*) > 1
        ) q
    """,
    "duplicate_order_item_keys": """
        SELECT COUNT(*) FROM (
            SELECT order_item_id FROM retail_sales.fact_order_items
            GROUP BY order_item_id HAVING COUNT(*) > 1
        ) q
    """,
    "duplicate_inventory_snapshot_keys": """
        SELECT COUNT(*) FROM (
            SELECT snapshot_date, asin, fulfillment_center_id
            FROM retail_inventory.fact_fba_inventory_daily
            GROUP BY snapshot_date, asin, fulfillment_center_id HAVING COUNT(*) > 1
        ) q
    """,
    "duplicate_review_keys": """
        SELECT COUNT(*) FROM (
            SELECT review_id FROM catalog.dim_reviews
            GROUP BY review_id HAVING COUNT(*) > 1
        ) q
    """,
    "duplicate_cart_keys": """
        SELECT COUNT(*) FROM (
            SELECT customer_id, asin, is_saved_for_later FROM customers.cart_items
            GROUP BY customer_id, asin, is_saved_for_later HAVING COUNT(*) > 1
        ) q
    """,
    "duplicate_wishlist_keys": """
        SELECT COUNT(*) FROM (
            SELECT customer_id, asin FROM customers.wishlists
            GROUP BY customer_id, asin HAVING COUNT(*) > 1
        ) q
    """,
    "products_without_category": """
        SELECT COUNT(*) FROM catalog.dim_products p
        LEFT JOIN catalog.dim_categories c ON c.category_id = p.category_id
        WHERE c.category_id IS NULL
    """,
    "invalid_product_prices_or_ratings": """
        SELECT COUNT(*) FROM catalog.dim_products
        WHERE standard_price < 0 OR original_price < 0 OR rating NOT BETWEEN 0 AND 5
    """,
    "traffic_orphan_product_or_customer": """
        SELECT COUNT(*) FROM retail_traffic.fact_glance_views v
        LEFT JOIN catalog.dim_products p ON p.asin = v.asin
        LEFT JOIN customers.dim_customers c ON c.customer_id = v.customer_id
        WHERE p.asin IS NULL OR c.customer_id IS NULL
    """,
    "order_orphan_customer": """
        SELECT COUNT(*) FROM retail_sales.fact_orders o
        LEFT JOIN customers.dim_customers c ON c.customer_id = o.customer_id
        WHERE c.customer_id IS NULL
    """,
    "order_items_orphan_order_or_product": """
        SELECT COUNT(*) FROM retail_sales.fact_order_items i
        LEFT JOIN retail_sales.fact_orders o ON o.order_id = i.order_id
        LEFT JOIN catalog.dim_products p ON p.asin = i.asin
        WHERE o.order_id IS NULL OR p.asin IS NULL
    """,
    "inventory_orphan_product_or_center": """
        SELECT COUNT(*) FROM retail_inventory.fact_fba_inventory_daily i
        LEFT JOIN catalog.dim_products p ON p.asin = i.asin
        LEFT JOIN fulfillment.dim_fulfillment_centers f
          ON f.fulfillment_center_id = i.fulfillment_center_id
        WHERE p.asin IS NULL OR f.fulfillment_center_id IS NULL
    """,
    "review_orphan_product_or_customer": """
        SELECT COUNT(*) FROM catalog.dim_reviews r
        LEFT JOIN catalog.dim_products p ON p.asin = r.asin
        LEFT JOIN customers.dim_customers c ON c.customer_id = r.customer_id
        WHERE p.asin IS NULL OR c.customer_id IS NULL
    """,
    "review_ratings_out_of_range": """
        SELECT COUNT(*) FROM catalog.dim_reviews WHERE rating NOT BETWEEN 1 AND 5
    """,
    "cart_orphan_customer_or_product": """
        SELECT COUNT(*) FROM customers.cart_items i
        LEFT JOIN catalog.dim_products p ON p.asin = i.asin
        LEFT JOIN customers.dim_customers c ON c.customer_id = i.customer_id
        WHERE p.asin IS NULL OR c.customer_id IS NULL
    """,
    "wishlist_orphan_customer_or_product": """
        SELECT COUNT(*) FROM customers.wishlists i
        LEFT JOIN catalog.dim_products p ON p.asin = i.asin
        LEFT JOIN customers.dim_customers c ON c.customer_id = i.customer_id
        WHERE p.asin IS NULL OR c.customer_id IS NULL
    """,
    "negative_inventory_or_reservations": """
        SELECT COUNT(*) FROM retail_inventory.fact_fba_inventory_daily
        WHERE units_in_stock < 0 OR units_reserved < 0
    """,
    "inventory_stockout_flag_mismatches": """
        SELECT COUNT(*) FROM retail_inventory.fact_fba_inventory_daily
        WHERE out_of_stock_flag IS DISTINCT FROM (units_in_stock = 0)
    """,
    "order_items_with_invalid_values": """
        SELECT COUNT(*) FROM retail_sales.fact_order_items
        WHERE ordered_units <= 0 OR item_price < 0 OR net_revenue < 0
    """,
    "orders_without_line_items": """
        SELECT COUNT(*) FROM retail_sales.fact_orders o
        LEFT JOIN retail_sales.fact_order_items i ON i.order_id = o.order_id
        WHERE i.order_id IS NULL
    """,
    "orders_total_vs_item_line_mismatches": """
        SELECT COUNT(*) FROM (
            SELECT o.order_id
            FROM retail_sales.fact_orders o
            LEFT JOIN retail_sales.fact_order_items i ON i.order_id = o.order_id
            GROUP BY o.order_id, o.total_amount
            HAVING ABS(COALESCE(o.total_amount, 0) - COALESCE(SUM(i.net_revenue), 0)) > 0.02
        ) q
    """,
}


def _write_query_csv(connection: Any, query: str, destination: Path) -> int:
    """Stream a query result to CSV so extraction memory stays bounded."""
    cursor_name = f"aislewise_{destination.stem}"
    row_count = 0
    with connection.cursor(name=cursor_name) as cursor:
        cursor.itersize = BATCH_SIZE
        cursor.execute(query)
        rows = cursor.fetchmany(BATCH_SIZE)
        columns = [description.name for description in cursor.description]
        with destination.open("w", newline="", encoding="utf-8") as output:
            writer = csv.writer(output)
            writer.writerow(columns)
            while rows:
                writer.writerows(rows)
                row_count += len(rows)
                rows = cursor.fetchmany(BATCH_SIZE)
    return row_count


def _table_counts(connection: Any) -> dict[str, int]:
    counts = {}
    with connection.cursor() as cursor:
        for table in SOURCE_TABLES:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            counts[table] = int(cursor.fetchone()[0])
    return counts


def _validate_schema(connection: Any) -> dict[str, list[str]]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT table_schema || '.' || table_name, column_name
            FROM information_schema.columns
            WHERE table_schema IN (
                'catalog', 'customers', 'fulfillment',
                'retail_inventory', 'retail_sales', 'retail_traffic'
            )
            """
        )
        available: dict[str, set[str]] = {}
        for table_name, column_name in cursor.fetchall():
            available.setdefault(table_name, set()).add(column_name)

    missing = {
        table_name: sorted(required - available.get(table_name, set()))
        for table_name, required in REQUIRED_COLUMNS.items()
        if required - available.get(table_name, set())
    }
    if missing:
        raise RuntimeError(f"Database schema is missing required columns: {missing}")
    return {table_name: sorted(required) for table_name, required in REQUIRED_COLUMNS.items()}


def _quality_results(connection: Any) -> dict[str, int]:
    results = {}
    with connection.cursor() as cursor:
        for check_name, query in QUALITY_QUERIES.items():
            cursor.execute(query)
            results[check_name] = int(cursor.fetchone()[0])
    return results


def _duckdb_analytics(output_dir: Path) -> dict[str, int]:
    """Create product, category, brand, and discount analyses from sanitized CSVs."""
    db = duckdb.connect(":memory:")
    try:
        filenames = (
            "products.csv",
            "traffic_daily.csv",
            "product_sales.csv",
            "reviews_by_product.csv",
            "shopping_intent_by_product.csv",
            "product_performance.csv",
            "product_segmentation_recommendations.csv",
            "category_performance.csv",
            "brand_performance.csv",
            "discount_effectiveness.csv",
        )
        paths = {
            name: str((output_dir / name).resolve()).replace("'", "''")
            for name in filenames
        }
        db.execute(
            f"""
            COPY (
                WITH traffic AS (
                    SELECT asin, SUM(view_events) AS traffic_event_count
                    FROM read_csv_auto('{paths['traffic_daily.csv']}')
                    GROUP BY asin
                )
                SELECT p.asin, p.product_title, p.brand, p.category, p.department,
                       p.standard_price, p.original_price, p.discount_percent,
                       p.rating, p.rating_count, p.inventory_snapshot_date,
                       p.latest_inventory_units, p.latest_reserved_units,
                       COALESCE(t.traffic_event_count, 0) AS traffic_event_count,
                       COALESCE(s.order_line_count, 0) AS order_line_count,
                       COALESCE(s.units_sold, 0) AS units_sold,
                       COALESCE(s.item_line_net_revenue, 0) AS item_line_net_revenue,
                       COALESCE(r.review_count, 0) AS review_count,
                       r.average_review_rating,
                       COALESCE(r.low_rating_review_count, 0) AS low_rating_review_count,
                       COALESCE(r.high_rating_review_count, 0) AS high_rating_review_count,
                       COALESCE(i.active_cart_lines, 0) AS active_cart_lines,
                       COALESCE(i.active_cart_units, 0) AS active_cart_units,
                       COALESCE(i.saved_cart_lines, 0) AS saved_cart_lines,
                       COALESCE(i.wishlist_additions, 0) AS wishlist_additions,
                       CASE
                           WHEN p.rating >= 4.2 AND COALESCE(t.traffic_event_count, 0) >= 20
                               THEN 'Stars (High Traffic, High Rating)'
                           WHEN p.rating >= 4.2 THEN 'Hidden Gems (Low Traffic, High Rating)'
                           WHEN COALESCE(t.traffic_event_count, 0) >= 20
                               THEN 'At Risk (High Traffic, Low Rating)'
                           ELSE 'Dead Weight (Low Traffic, Low Rating)'
                       END AS segment
                FROM read_csv_auto('{paths['products.csv']}') p
                LEFT JOIN traffic t USING (asin)
                LEFT JOIN read_csv_auto('{paths['product_sales.csv']}') s USING (asin)
                LEFT JOIN read_csv_auto('{paths['reviews_by_product.csv']}') r USING (asin)
                LEFT JOIN read_csv_auto('{paths['shopping_intent_by_product.csv']}') i USING (asin)
                ORDER BY p.asin
            ) TO '{paths['product_performance.csv']}'
              (HEADER, DELIMITER ',')
            """
        )
        db.execute(
            f"""
            COPY (
                SELECT asin, product_title, brand, category, department,
                       standard_price, original_price, discount_percent,
                       rating AS average_rating, rating_count,
                       inventory_snapshot_date, latest_inventory_units,
                       latest_reserved_units,
                       traffic_event_count AS total_views,
                       order_line_count, units_sold, item_line_net_revenue,
                       review_count, average_review_rating,
                       low_rating_review_count, high_rating_review_count,
                       active_cart_lines, active_cart_units, saved_cart_lines,
                       wishlist_additions, segment
                FROM read_csv_auto('{paths['product_performance.csv']}')
                ORDER BY asin
            ) TO '{paths['product_segmentation_recommendations.csv']}'
              (HEADER, DELIMITER ',')
            """
        )
        db.execute(
            f"""
            COPY (
                SELECT category, department, COUNT(*) AS product_count,
                       SUM(traffic_event_count) AS traffic_events,
                       SUM(units_sold) AS units_sold,
                       SUM(item_line_net_revenue) AS item_line_net_revenue,
                       AVG(rating) AS mean_product_rating,
                       SUM(latest_inventory_units) AS latest_inventory_units
                FROM read_csv_auto('{paths['product_performance.csv']}')
                GROUP BY category, department ORDER BY item_line_net_revenue DESC
            ) TO '{paths['category_performance.csv']}'
              (HEADER, DELIMITER ',')
            """
        )
        db.execute(
            f"""
            COPY (
                SELECT brand, COUNT(*) AS product_count,
                       SUM(traffic_event_count) AS traffic_events,
                       SUM(units_sold) AS units_sold,
                       SUM(item_line_net_revenue) AS item_line_net_revenue,
                       AVG(rating) AS mean_product_rating
                FROM read_csv_auto('{paths['product_performance.csv']}')
                GROUP BY brand ORDER BY item_line_net_revenue DESC
            ) TO '{paths['brand_performance.csv']}'
              (HEADER, DELIMITER ',')
            """
        )
        db.execute(
            f"""
            COPY (
                SELECT CASE
                           WHEN discount_percent <= 0 THEN '0%'
                           WHEN discount_percent < 10 THEN '1-9%'
                           WHEN discount_percent < 20 THEN '10-19%'
                           WHEN discount_percent < 40 THEN '20-39%'
                           ELSE '40%+'
                       END AS discount_band,
                       COUNT(*) AS product_count,
                       AVG(traffic_event_count) AS mean_traffic_events_per_product,
                       SUM(units_sold) AS units_sold,
                       SUM(item_line_net_revenue) AS item_line_net_revenue
                FROM read_csv_auto('{paths['product_performance.csv']}')
                GROUP BY discount_band ORDER BY MIN(discount_percent)
            ) TO '{paths['discount_effectiveness.csv']}'
              (HEADER, DELIMITER ',')
            """
        )
        outputs = (
            "product_performance.csv",
            "product_segmentation_recommendations.csv",
            "category_performance.csv",
            "brand_performance.csv",
            "discount_effectiveness.csv",
        )
        return {
            name: int(
                db.execute(
                    f"SELECT COUNT(*) FROM read_csv_auto('{paths[name]}')"
                ).fetchone()[0]
            )
            for name in outputs
        }
    finally:
        db.close()


def _validate_export_completeness(
    output_dir: Path,
    source_counts: dict[str, int],
) -> dict[str, int]:
    """Reconcile key record totals using DuckDB without loading entire exports."""
    paths = {
        name: str((output_dir / name).resolve()).replace("'", "''")
        for name in (
            "products.csv",
            "traffic_daily.csv",
            "orders_daily.csv",
            "product_sales.csv",
            "customer_segments.csv",
            "reviews_by_product.csv",
            "review_rating_distribution.csv",
            "shopping_intent_by_product.csv",
        )
    }
    db = duckdb.connect(":memory:")
    try:
        checks = {
            "product_rows_match_source": (
                f"SELECT COUNT(*) FROM read_csv_auto('{paths['products.csv']}')",
                source_counts["catalog.dim_products"],
            ),
            "product_asins_unique": (
                f"SELECT COUNT(DISTINCT asin) FROM read_csv_auto('{paths['products.csv']}')",
                source_counts["catalog.dim_products"],
            ),
            "traffic_events_match_source": (
                f"SELECT SUM(view_events) FROM read_csv_auto('{paths['traffic_daily.csv']}')",
                source_counts["retail_traffic.fact_glance_views"],
            ),
            "orders_match_source": (
                f"SELECT SUM(order_count) FROM read_csv_auto('{paths['orders_daily.csv']}')",
                source_counts["retail_sales.fact_orders"],
            ),
            "order_lines_match_source": (
                f"SELECT SUM(order_line_count) FROM read_csv_auto('{paths['product_sales.csv']}')",
                source_counts["retail_sales.fact_order_items"],
            ),
            "customers_match_source": (
                f"SELECT SUM(customer_count) FROM read_csv_auto('{paths['customer_segments.csv']}')",
                source_counts["customers.dim_customers"],
            ),
            "reviews_match_source": (
                f"SELECT SUM(review_count) FROM read_csv_auto('{paths['review_rating_distribution.csv']}')",
                source_counts["catalog.dim_reviews"],
            ),
            "shopping_intent_products_match_catalog": (
                f"SELECT COUNT(*) FROM read_csv_auto('{paths['shopping_intent_by_product.csv']}')",
                source_counts["catalog.dim_products"],
            ),
        }
        observed = {}
        failures = {}
        for check_name, (query, expected) in checks.items():
            db_value = db.execute(query).fetchone()[0]
            actual = int(db_value or 0)
            observed[check_name] = actual
            if actual != expected:
                failures[check_name] = {"expected": expected, "actual": actual}

        sensitive_columns = {
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
        for filename in paths:
            with (output_dir / filename).open(
                "r", newline="", encoding="utf-8"
            ) as source:
                columns = set(next(csv.reader(source)))
            prohibited = sorted(columns.intersection(sensitive_columns))
            if prohibited:
                failures[f"privacy_columns_absent:{filename}"] = prohibited

        if failures:
            raise ValueError(f"Expanded export validation failed: {failures}")
        return observed
    finally:
        db.close()


def build_analytics_snapshot(output_path: Path = OUTPUT_PATH) -> dict[str, Any]:
    """Extract sanitized aggregates, validate them, and derive DuckDB analytics."""
    output_path.mkdir(parents=True, exist_ok=True)
    source_counts: dict[str, int] = {}
    output_counts = {}
    with database_connection() as connection:
        connection.set_session(readonly=True)
        schema = _validate_schema(connection)
        source_counts = _table_counts(connection)
        quality = _quality_results(connection)
        for filename, query in EXTRACT_QUERIES.items():
            output_counts[filename] = _write_query_csv(
                connection, query, output_path / filename
            )
            logger.info("Extracted %s rows to %s", output_counts[filename], filename)

    export_reconciliation = _validate_export_completeness(
        output_path, source_counts
    )
    derived_counts = _duckdb_analytics(output_path)
    observed_record_total = sum(source_counts.values())
    quality_report = {
        "source_table_rows": source_counts,
        "observed_rows_across_extracted_tables": observed_record_total,
        "validated_schema_columns": schema,
        "export_reconciliation": export_reconciliation,
        "checks": quality,
        "order_total_reconciliation": {
            "orders_with_total_differing_from_item_line_net_revenue_over_0_02": quality[
                "orders_total_vs_item_line_mismatches"
            ],
            "interpretation": (
                "Reported as a reconciliation exception. Order totals and line net revenue "
                "may use different business definitions; no profit or conversion rate is inferred."
            ),
        },
        "persisted_outputs": {
            **output_counts,
            **derived_counts,
        },
        "privacy": {
            "customer_ids_exported": False,
            "emails_or_addresses_exported": False,
            "reviewer_names_or_text_exported": False,
            "order_ids_or_tracking_numbers_exported": False,
            "traffic_is_event_count_not_unique_visitors": True,
        },
    }
    (output_path / "data_quality.json").write_text(
        json.dumps(quality_report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest = {
        "dataset_version": "aislewise-retail-analytics-v1",
        "source": "Existing Neon PostgreSQL database; read-only transaction",
        "extracted_at_utc": datetime.now(timezone.utc).isoformat(),
        "product_rows": source_counts["catalog.dim_products"],
        "observed_rows_across_extracted_tables": observed_record_total,
        "export_reconciliation": export_reconciliation,
        "source_table_rows": source_counts,
        "persisted_output_rows": {**output_counts, **derived_counts},
        "quality_report": "data_quality.json",
        "privacy_note": (
            "Only catalog product attributes and aggregated behavior are persisted. "
            "No customer identifiers, contact details, raw review text, order IDs, or tracking numbers."
        ),
    }
    (output_path / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    logger.info(
        "Completed snapshot: %s products, %s traffic events, %s orders, %s item rows",
        source_counts["catalog.dim_products"],
        source_counts["retail_traffic.fact_glance_views"],
        source_counts["retail_sales.fact_orders"],
        source_counts["retail_sales.fact_order_items"],
    )
    return manifest

if __name__ == "__main__":
    build_analytics_snapshot()
