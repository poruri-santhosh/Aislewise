import json
import logging
import os
import random
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from typing import Any, Dict, Iterator, Optional

import psycopg2
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, session
from psycopg2.extras import RealDictCursor
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
secret_key = os.getenv("FLASK_SECRET_KEY")
if os.getenv("VERCEL") and not secret_key:
    raise RuntimeError("FLASK_SECRET_KEY must be set in the Vercel project environment.")
app.secret_key = secret_key or "local-development-only-change-me"

DEMO_CUSTOMER_EMAIL = "demo@amazon-clone.local"


class DatabaseConfigurationError(Exception):
    pass


@contextmanager
def database_connection() -> Iterator[psycopg2.extensions.connection]:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise DatabaseConfigurationError(
            "DATABASE_URL is not set. Add your Neon connection URL to .env."
        )

    connection = psycopg2.connect(
        database_url,
        sslmode="require",
        connect_timeout=15,
    )
    try:
        yield connection
    finally:
        connection.close()


def api_error(message: str, status_code: int = 400):
    return jsonify({"error": message}), status_code


def api_database_error():
    app.logger.exception("Neon database operation failed")
    return jsonify({"error": "A database operation failed. Please try again."}), 503


def get_current_customer_id(cursor) -> int:
    """Return customer_id from session if logged in, else fallback to demo customer."""
    cust_id = session.get("customer_id")
    if cust_id:
        cursor.execute("SELECT customer_id FROM customers.dim_customers WHERE customer_id = %s", (cust_id,))
        row = cursor.fetchone()
        if row:
            return row[0]

    # Fallback to demo customer
    cursor.execute("SELECT customer_id FROM customers.dim_customers WHERE email = %s", (DEMO_CUSTOMER_EMAIL,))
    row = cursor.fetchone()
    if row:
        session["customer_id"] = row[0]
        return row[0]

    # Create demo customer if doesn't exist
    cursor.execute("""
        INSERT INTO customers.dim_customers
            (name, email, password_hash, shipping_address, city, postal_code, signup_date)
        VALUES ('Alex Mercer', %s, %s, '410 Terry Ave N', 'Seattle', '98109', CURRENT_DATE)
        ON CONFLICT (email) DO NOTHING
        RETURNING customer_id
    """, (DEMO_CUSTOMER_EMAIL, generate_password_hash("amazonpassword123")))
    new_row = cursor.fetchone()
    if new_row:
        cid = new_row[0]
    else:
        cursor.execute("SELECT customer_id FROM customers.dim_customers WHERE email = %s", (DEMO_CUSTOMER_EMAIL,))
        cid = cursor.fetchone()[0]

    session["customer_id"] = cid
    return cid


def get_customer_info(cursor, customer_id: int) -> Dict[str, Any]:
    cursor.execute("""
        SELECT customer_id, name, email, customer_segment, shipping_address, city, postal_code, country_code
        FROM customers.dim_customers
        WHERE customer_id = %s
    """, (customer_id,))
    row = cursor.fetchone()
    if not row:
        return {}
    return {
        "customer_id": row[0],
        "name": row[1] or "Amazon Customer",
        "email": row[2],
        "customer_segment": row[3] or "Prime",
        "shipping_address": row[4] or "410 Terry Ave N",
        "city": row[5] or "Seattle",
        "postal_code": row[6] or "98109",
        "country_code": row[7] or "US"
    }


# ==========================================
# PAGE ROUTES
# ==========================================

@app.get("/")
def index():
    try:
        with database_connection() as conn:
            with conn.cursor() as cur:
                customer_id = get_current_customer_id(cur)
                customer = get_customer_info(cur, customer_id)

                # Fetch distinct categories and departments
                cur.execute("""
                    SELECT c.category_id, c.category_name, c.department, COALESCE(c.icon, 'fa-tag'),
                           COUNT(p.asin) as product_count
                    FROM catalog.dim_categories c
                    LEFT JOIN catalog.dim_products p ON p.category_id = c.category_id
                    GROUP BY c.category_id, c.category_name, c.department, c.icon
                    ORDER BY c.department, c.category_name
                """)
                categories = [
                    {
                        "category_id": r[0],
                        "category_name": r[1],
                        "department": r[2],
                        "icon": r[3],
                        "product_count": r[4]
                    }
                    for r in cur.fetchall()
                ]

                # Fetch cart items count
                cur.execute("""
                    SELECT COALESCE(SUM(quantity), 0)
                    FROM customers.cart_items
                    WHERE customer_id = %s AND is_saved_for_later = FALSE
                """, (customer_id,))
                cart_count = cur.fetchone()[0]

                # Fetch featured initial products
                cur.execute("""
                    SELECT p.asin, p.product_title, p.brand, p.standard_price, p.original_price,
                           p.discount_percent, p.rating, p.rating_count, p.image_url,
                           p.is_prime_eligible, p.is_best_seller, p.is_amazons_choice,
                           c.category_name, c.department,
                           COALESCE(SUM(i.units_in_stock), 0) as units_in_stock
                    FROM catalog.dim_products p
                    LEFT JOIN catalog.dim_categories c ON c.category_id = p.category_id
                    LEFT JOIN retail_inventory.fact_fba_inventory_daily i
                        ON i.asin = p.asin
                        AND i.snapshot_date = (
                            SELECT MAX(inventory.snapshot_date)
                            FROM retail_inventory.fact_fba_inventory_daily inventory
                            WHERE inventory.asin = p.asin
                        )
                    GROUP BY p.asin, p.product_title, p.brand, p.standard_price, p.original_price,
                             p.discount_percent, p.rating, p.rating_count, p.image_url,
                             p.is_prime_eligible, p.is_best_seller, p.is_amazons_choice,
                             c.category_name, c.department
                    ORDER BY p.is_best_seller DESC, p.rating DESC, p.product_title ASC
                """)
                products = [
                    {
                        "asin": r[0],
                        "title": r[1],
                        "brand": r[2],
                        "price": float(r[3]),
                        "original_price": float(r[4]) if r[4] else None,
                        "discount_percent": r[5] or 0,
                        "rating": float(r[6]) if r[6] else 4.5,
                        "rating_count": r[7] or 0,
                        "image_url": r[8] or "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=500",
                        "is_prime": bool(r[9]),
                        "is_best_seller": bool(r[10]),
                        "is_amazons_choice": bool(r[11]),
                        "category": r[12] or "General",
                        "department": r[13] or "All",
                        "units_in_stock": int(r[14]),
                    }
                    for r in cur.fetchall()
                ]

        return render_template(
            "index.html",
            customer=customer,
            categories=categories,
            products=products,
            cart_count=cart_count,
        )
    except psycopg2.Error:
        return api_database_error()
    except DatabaseConfigurationError as e:
        return api_error(str(e), 503)


# ==========================================
# PRODUCT & CATALOG APIS
# ==========================================

@app.get("/api/products")
def get_products():
    """Search, filter, and sort products."""
    category = request.args.get("category")
    department = request.args.get("department")
    query = request.args.get("q", "").strip()
    brand = request.args.get("brand")
    min_price = request.args.get("min_price", type=float)
    max_price = request.args.get("max_price", type=float)
    min_rating = request.args.get("min_rating", type=float)
    prime_only = request.args.get("prime_only") == "true"
    deals_only = request.args.get("deals_only") == "true"
    best_sellers_only = request.args.get("best_sellers_only") == "true"
    sort_by = request.args.get("sort", "featured")

    sql = """
        SELECT p.asin, p.product_title, p.brand, p.standard_price, p.original_price,
               p.discount_percent, p.rating, p.rating_count, p.image_url,
               p.is_prime_eligible, p.is_best_seller, p.is_amazons_choice,
               c.category_name, c.department,
               COALESCE(SUM(i.units_in_stock), 0) as units_in_stock
        FROM catalog.dim_products p
        LEFT JOIN catalog.dim_categories c ON c.category_id = p.category_id
        LEFT JOIN retail_inventory.fact_fba_inventory_daily i
            ON i.asin = p.asin
            AND i.snapshot_date = (
                SELECT MAX(inventory.snapshot_date)
                FROM retail_inventory.fact_fba_inventory_daily inventory
                WHERE inventory.asin = p.asin
            )
        WHERE 1=1
    """
    params = []

    if category and category.lower() != "all":
        sql += " AND (LOWER(c.category_name) = LOWER(%s) OR LOWER(c.department) = LOWER(%s))"
        params.extend([category, category])

    if department and department.lower() != "all":
        sql += " AND LOWER(c.department) = LOWER(%s)"
        params.append(department)

    if query:
        sql += """ AND (
            p.product_title ILIKE %s OR
            p.brand ILIKE %s OR
            p.description ILIKE %s OR
            c.category_name ILIKE %s OR
            c.department ILIKE %s OR
            p.asin ILIKE %s
        )"""
        q_param = f"%{query}%"
        params.extend([q_param, q_param, q_param, q_param, q_param, q_param])

    if brand:
        sql += " AND LOWER(p.brand) = LOWER(%s)"
        params.append(brand)

    if min_price is not None:
        sql += " AND p.standard_price >= %s"
        params.append(min_price)

    if max_price is not None:
        sql += " AND p.standard_price <= %s"
        params.append(max_price)

    if min_rating is not None:
        sql += " AND p.rating >= %s"
        params.append(min_rating)

    if prime_only:
        sql += " AND p.is_prime_eligible = TRUE"

    if deals_only:
        sql += " AND p.discount_percent >= 10"

    if best_sellers_only:
        sql += " AND p.is_best_seller = TRUE"

    sql += """
        GROUP BY p.asin, p.product_title, p.brand, p.standard_price, p.original_price,
                 p.discount_percent, p.rating, p.rating_count, p.image_url,
                 p.is_prime_eligible, p.is_best_seller, p.is_amazons_choice,
                 c.category_name, c.department
    """

    if sort_by == "price_low":
        sql += " ORDER BY p.standard_price ASC"
    elif sort_by == "price_high":
        sql += " ORDER BY p.standard_price DESC"
    elif sort_by == "rating":
        sql += " ORDER BY p.rating DESC, p.rating_count DESC"
    elif sort_by == "newest":
        sql += " ORDER BY p.created_at DESC"
    else:  # featured
        sql += " ORDER BY p.is_best_seller DESC, p.is_amazons_choice DESC, p.rating DESC, p.product_title ASC"

    try:
        with database_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, tuple(params))
                rows = cur.fetchall()
                products = [
                    {
                        "asin": r[0],
                        "title": r[1],
                        "brand": r[2],
                        "price": float(r[3]),
                        "original_price": float(r[4]) if r[4] else None,
                        "discount_percent": r[5] or 0,
                        "rating": float(r[6]) if r[6] else 4.5,
                        "rating_count": r[7] or 0,
                        "image_url": r[8] or "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=500",
                        "is_prime": bool(r[9]),
                        "is_best_seller": bool(r[10]),
                        "is_amazons_choice": bool(r[11]),
                        "category": r[12] or "General",
                        "department": r[13] or "All",
                        "units_in_stock": int(r[14]),
                    }
                    for r in rows
                ]
        return jsonify({"products": products, "count": len(products)})
    except psycopg2.Error:
        return api_database_error()


@app.get("/api/products/<asin>")
def get_product_detail(asin: str):
    """Retrieve full product detail with gallery, features, specs, stock and reviews."""
    try:
        with database_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT p.asin, p.product_title, p.brand, p.standard_price, p.original_price,
                           p.discount_percent, p.rating, p.rating_count, p.image_url,
                           p.additional_images, p.description, p.features,
                           p.is_prime_eligible, p.is_best_seller, p.is_amazons_choice,
                           c.category_name, c.department,
                           COALESCE(SUM(i.units_in_stock), 0) as units_in_stock
                    FROM catalog.dim_products p
                    LEFT JOIN catalog.dim_categories c ON c.category_id = p.category_id
                    LEFT JOIN retail_inventory.fact_fba_inventory_daily i
                        ON i.asin = p.asin
                        AND i.snapshot_date = (
                            SELECT MAX(inventory.snapshot_date)
                            FROM retail_inventory.fact_fba_inventory_daily inventory
                            WHERE inventory.asin = p.asin
                        )
                    WHERE p.asin = %s
                    GROUP BY p.asin, p.product_title, p.brand, p.standard_price, p.original_price,
                             p.discount_percent, p.rating, p.rating_count, p.image_url,
                             p.additional_images, p.description, p.features,
                             p.is_prime_eligible, p.is_best_seller, p.is_amazons_choice,
                             c.category_name, c.department
                """, (asin,))
                row = cur.fetchone()
                if not row:
                    return api_error("Product not found", 404)

                add_imgs = row[9]
                if isinstance(add_imgs, str):
                    try:
                        add_imgs = json.loads(add_imgs)
                    except Exception:
                        add_imgs = []
                elif not isinstance(add_imgs, list):
                    add_imgs = []

                features = row[11]
                if isinstance(features, str):
                    try:
                        features = json.loads(features)
                    except Exception:
                        features = []
                elif not isinstance(features, list):
                    features = []

                # Fetch verified customer reviews for this product
                cur.execute("""
                    SELECT review_id, customer_name, rating, review_title, review_text,
                           is_verified_purchase, created_at
                    FROM catalog.dim_reviews
                    WHERE asin = %s
                    ORDER BY created_at DESC
                """, (asin,))
                reviews = [
                    {
                        "review_id": rev[0],
                        "customer_name": rev[1],
                        "rating": rev[2],
                        "title": rev[3],
                        "text": rev[4],
                        "is_verified": bool(rev[5]),
                        "date": rev[6].strftime("%B %d, %Y") if rev[6] else "Recent"
                    }
                    for rev in cur.fetchall()
                ]

                # Check if current user has this item in wishlist
                cust_id = get_current_customer_id(cur)
                cur.execute("SELECT 1 FROM customers.wishlists WHERE customer_id = %s AND asin = %s", (cust_id, asin))
                in_wishlist = cur.fetchone() is not None

                product = {
                    "asin": row[0],
                    "title": row[1],
                    "brand": row[2],
                    "price": float(row[3]),
                    "original_price": float(row[4]) if row[4] else None,
                    "discount_percent": row[5] or 0,
                    "rating": float(row[6]) if row[6] else 4.5,
                    "rating_count": row[7] or 0,
                    "image_url": row[8],
                    "additional_images": add_imgs,
                    "description": row[10] or "",
                    "features": features,
                    "is_prime": bool(row[12]),
                    "is_best_seller": bool(row[13]),
                    "is_amazons_choice": bool(row[14]),
                    "category": row[15] or "General",
                    "department": row[16] or "All",
                    "units_in_stock": int(row[17]),
                    "reviews": reviews,
                    "in_wishlist": in_wishlist
                }
        return jsonify(product)
    except psycopg2.Error:
        return api_database_error()


@app.get("/api/search/suggestions")
def search_suggestions():
    """Real-time autocomplete dropdown suggestions."""
    q = request.args.get("q", "").strip()
    if not q or len(q) < 2:
        return jsonify([])

    try:
        with database_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT asin, product_title, standard_price, image_url, brand
                    FROM catalog.dim_products
                    WHERE product_title ILIKE %s OR brand ILIKE %s
                    ORDER BY rating_count DESC
                    LIMIT 6
                """, (f"%{q}%", f"%{q}%"))
                suggestions = [
                    {
                        "asin": r[0],
                        "title": r[1],
                        "price": float(r[2]),
                        "image_url": r[3],
                        "brand": r[4]
                    }
                    for r in cur.fetchall()
                ]
        return jsonify(suggestions)
    except psycopg2.Error:
        return api_database_error()


@app.get("/api/categories")
def get_categories():
    """Retrieve all categories and departments with product count."""
    try:
        with database_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT c.category_id, c.category_name, c.department, COALESCE(c.icon, 'fa-tag'),
                           COUNT(p.asin) as count
                    FROM catalog.dim_categories c
                    LEFT JOIN catalog.dim_products p ON p.category_id = c.category_id
                    GROUP BY c.category_id, c.category_name, c.department, c.icon
                    ORDER BY c.department, c.category_name
                """)
                cats = [
                    {
                        "id": r[0],
                        "name": r[1],
                        "department": r[2],
                        "icon": r[3],
                        "count": r[4]
                    }
                    for r in cur.fetchall()
                ]
        return jsonify(cats)
    except psycopg2.Error:
        return api_database_error()


# ==========================================
# CART APIS
# ==========================================

@app.get("/api/cart")
def get_cart():
    """Get active cart items and saved for later items with subtotal."""
    try:
        with database_connection() as conn:
            with conn.cursor() as cur:
                cust_id = get_current_customer_id(cur)
                cur.execute("""
                    SELECT c.cart_item_id, c.asin, c.quantity, c.is_saved_for_later,
                           p.product_title, p.standard_price, p.image_url, p.brand,
                           p.is_prime_eligible,
                           COALESCE(SUM(i.units_in_stock), 0) as units_in_stock
                    FROM customers.cart_items c
                    JOIN catalog.dim_products p ON p.asin = c.asin
                    LEFT JOIN retail_inventory.fact_fba_inventory_daily i
                        ON i.asin = p.asin
                        AND i.snapshot_date = (
                            SELECT MAX(inventory.snapshot_date)
                            FROM retail_inventory.fact_fba_inventory_daily inventory
                            WHERE inventory.asin = p.asin
                        )
                    WHERE c.customer_id = %s
                    GROUP BY c.cart_item_id, c.asin, c.quantity, c.is_saved_for_later,
                             p.product_title, p.standard_price, p.image_url, p.brand,
                             p.is_prime_eligible
                    ORDER BY c.updated_at DESC
                """, (cust_id,))

                items = []
                saved_items = []
                subtotal = 0.0
                total_count = 0

                for r in cur.fetchall():
                    item = {
                        "cart_item_id": r[0],
                        "asin": r[1],
                        "quantity": r[2],
                        "is_saved": bool(r[3]),
                        "title": r[4],
                        "price": float(r[5]),
                        "image_url": r[6],
                        "brand": r[7],
                        "is_prime": bool(r[8]),
                        "units_in_stock": int(r[9]),
                        "total_price": float(r[5]) * r[2]
                    }
                    if item["is_saved"]:
                        saved_items.append(item)
                    else:
                        items.append(item)
                        subtotal += item["total_price"]
                        total_count += item["quantity"]

        return jsonify({
            "items": items,
            "saved_items": saved_items,
            "subtotal": round(subtotal, 2),
            "count": total_count,
            "qualifies_free_shipping": subtotal >= 35.0 or subtotal == 0
        })
    except psycopg2.Error:
        return api_database_error()


@app.post("/api/cart/add")
def add_to_cart():
    """Add or increment product quantity in cart."""
    data = request.get_json(silent=True) or {}
    asin = data.get("asin")
    qty = int(data.get("quantity", 1))

    if not asin or qty < 1:
        return api_error("Invalid ASIN or quantity")

    try:
        with database_connection() as conn:
            with conn.cursor() as cur:
                cust_id = get_current_customer_id(cur)
                # Ensure product exists
                cur.execute("SELECT standard_price, product_title FROM catalog.dim_products WHERE asin = %s", (asin,))
                prod = cur.fetchone()
                if not prod:
                    return api_error("Product not found", 404)

                # Upsert into cart_items
                cur.execute("""
                    INSERT INTO customers.cart_items (customer_id, asin, quantity, is_saved_for_later, updated_at)
                    VALUES (%s, %s, %s, FALSE, CURRENT_TIMESTAMP)
                    ON CONFLICT (customer_id, asin, is_saved_for_later) DO UPDATE SET
                        quantity = customers.cart_items.quantity + EXCLUDED.quantity,
                        updated_at = CURRENT_TIMESTAMP
                    RETURNING cart_item_id, quantity
                """, (cust_id, asin, qty))
                cart_row = cur.fetchone()

                # Get new total cart count
                cur.execute("""
                    SELECT COALESCE(SUM(quantity), 0) FROM customers.cart_items
                    WHERE customer_id = %s AND is_saved_for_later = FALSE
                """, (cust_id,))
                total_count = cur.fetchone()[0]

            conn.commit()

        return jsonify({
            "message": f"Added {prod[1]} to cart",
            "asin": asin,
            "quantity": cart_row[1],
            "cart_count": total_count
        }), 201
    except psycopg2.Error:
        return api_database_error()


@app.post("/api/cart/update")
def update_cart_item():
    """Update item quantity or delete if quantity is 0."""
    data = request.get_json(silent=True) or {}
    asin = data.get("asin")
    qty = int(data.get("quantity", 1))

    if not asin:
        return api_error("ASIN required")

    try:
        with database_connection() as conn:
            with conn.cursor() as cur:
                cust_id = get_current_customer_id(cur)
                if qty <= 0:
                    cur.execute("""
                        DELETE FROM customers.cart_items
                        WHERE customer_id = %s AND asin = %s AND is_saved_for_later = FALSE
                    """, (cust_id, asin))
                else:
                    cur.execute("""
                        UPDATE customers.cart_items
                        SET quantity = %s, updated_at = CURRENT_TIMESTAMP
                        WHERE customer_id = %s AND asin = %s AND is_saved_for_later = FALSE
                    """, (qty, cust_id, asin))

                # New total count
                cur.execute("""
                    SELECT COALESCE(SUM(quantity), 0) FROM customers.cart_items
                    WHERE customer_id = %s AND is_saved_for_later = FALSE
                """, (cust_id,))
                total_count = cur.fetchone()[0]
            conn.commit()

        return jsonify({"message": "Cart updated", "cart_count": total_count})
    except psycopg2.Error:
        return api_database_error()


@app.post("/api/cart/remove")
def remove_from_cart():
    """Remove item from cart or saved for later."""
    data = request.get_json(silent=True) or {}
    asin = data.get("asin")
    if not asin:
        return api_error("ASIN required")

    try:
        with database_connection() as conn:
            with conn.cursor() as cur:
                cust_id = get_current_customer_id(cur)
                cur.execute("""
                    DELETE FROM customers.cart_items
                    WHERE customer_id = %s AND asin = %s
                """, (cust_id, asin))

                cur.execute("""
                    SELECT COALESCE(SUM(quantity), 0) FROM customers.cart_items
                    WHERE customer_id = %s AND is_saved_for_later = FALSE
                """, (cust_id,))
                total_count = cur.fetchone()[0]
            conn.commit()

        return jsonify({"message": "Item removed", "cart_count": total_count})
    except psycopg2.Error:
        return api_database_error()


@app.post("/api/cart/save-for-later")
def save_for_later():
    """Move item between active cart and saved for later."""
    data = request.get_json(silent=True) or {}
    asin = data.get("asin")
    if not asin:
        return api_error("ASIN required")

    try:
        with database_connection() as conn:
            with conn.cursor() as cur:
                cust_id = get_current_customer_id(cur)
                # Delete active cart item and insert as saved for later
                cur.execute("""
                    SELECT quantity FROM customers.cart_items
                    WHERE customer_id = %s AND asin = %s AND is_saved_for_later = FALSE
                """, (cust_id, asin))
                row = cur.fetchone()
                qty = row[0] if row else 1

                cur.execute("""
                    DELETE FROM customers.cart_items
                    WHERE customer_id = %s AND asin = %s AND is_saved_for_later = FALSE
                """, (cust_id, asin))

                cur.execute("""
                    INSERT INTO customers.cart_items (customer_id, asin, quantity, is_saved_for_later, updated_at)
                    VALUES (%s, %s, %s, TRUE, CURRENT_TIMESTAMP)
                    ON CONFLICT (customer_id, asin, is_saved_for_later) DO UPDATE SET
                        quantity = EXCLUDED.quantity,
                        updated_at = CURRENT_TIMESTAMP
                """, (cust_id, asin, qty))
            conn.commit()

        return jsonify({"message": "Item moved to Saved for Later"})
    except psycopg2.Error:
        return api_database_error()


@app.post("/api/cart/move-to-cart")
def move_to_cart():
    """Move item from saved for later back to active cart."""
    data = request.get_json(silent=True) or {}
    asin = data.get("asin")
    if not asin:
        return api_error("ASIN required")

    try:
        with database_connection() as conn:
            with conn.cursor() as cur:
                cust_id = get_current_customer_id(cur)
                cur.execute("""
                    SELECT quantity FROM customers.cart_items
                    WHERE customer_id = %s AND asin = %s AND is_saved_for_later = TRUE
                """, (cust_id, asin))
                row = cur.fetchone()
                qty = row[0] if row else 1

                cur.execute("""
                    DELETE FROM customers.cart_items
                    WHERE customer_id = %s AND asin = %s AND is_saved_for_later = TRUE
                """, (cust_id, asin))

                cur.execute("""
                    INSERT INTO customers.cart_items (customer_id, asin, quantity, is_saved_for_later, updated_at)
                    VALUES (%s, %s, %s, FALSE, CURRENT_TIMESTAMP)
                    ON CONFLICT (customer_id, asin, is_saved_for_later) DO UPDATE SET
                        quantity = customers.cart_items.quantity + EXCLUDED.quantity,
                        updated_at = CURRENT_TIMESTAMP
                """, (cust_id, asin, qty))
            conn.commit()

        return jsonify({"message": "Item moved back to cart"})
    except psycopg2.Error:
        return api_database_error()


# ==========================================
# WISHLIST APIS
# ==========================================

@app.get("/api/wishlist")
def get_wishlist():
    """Get all products in the customer's wishlist."""
    try:
        with database_connection() as conn:
            with conn.cursor() as cur:
                cust_id = get_current_customer_id(cur)
                cur.execute("""
                    SELECT w.wishlist_id, p.asin, p.product_title, p.brand, p.standard_price,
                           p.original_price, p.discount_percent, p.rating, p.image_url,
                           p.is_prime_eligible, w.added_at
                    FROM customers.wishlists w
                    JOIN catalog.dim_products p ON p.asin = w.asin
                    WHERE w.customer_id = %s
                    ORDER BY w.added_at DESC
                """, (cust_id,))
                items = [
                    {
                        "wishlist_id": r[0],
                        "asin": r[1],
                        "title": r[2],
                        "brand": r[3],
                        "price": float(r[4]),
                        "original_price": float(r[5]) if r[5] else None,
                        "discount_percent": r[6] or 0,
                        "rating": float(r[7]) if r[7] else 4.5,
                        "image_url": r[8],
                        "is_prime": bool(r[9]),
                        "added_at": r[10].strftime("%B %d, %Y") if r[10] else "Recently"
                    }
                    for r in cur.fetchall()
                ]
        return jsonify({"items": items, "count": len(items)})
    except psycopg2.Error:
        return api_database_error()


@app.post("/api/wishlist/toggle")
def toggle_wishlist():
    """Toggle product in user's wishlist."""
    data = request.get_json(silent=True) or {}
    asin = data.get("asin")
    if not asin:
        return api_error("ASIN required")

    try:
        with database_connection() as conn:
            with conn.cursor() as cur:
                cust_id = get_current_customer_id(cur)
                cur.execute("SELECT 1 FROM customers.wishlists WHERE customer_id = %s AND asin = %s", (cust_id, asin))
                exists = cur.fetchone() is not None

                if exists:
                    cur.execute("DELETE FROM customers.wishlists WHERE customer_id = %s AND asin = %s", (cust_id, asin))
                    in_wishlist = False
                    msg = "Removed from your Wish List"
                else:
                    cur.execute("INSERT INTO customers.wishlists (customer_id, asin) VALUES (%s, %s)", (cust_id, asin))
                    in_wishlist = True
                    msg = "Added to your Wish List"

                cur.execute("SELECT COUNT(*) FROM customers.wishlists WHERE customer_id = %s", (cust_id,))
                wishlist_count = cur.fetchone()[0]

            conn.commit()

        return jsonify({
            "message": msg,
            "in_wishlist": in_wishlist,
            "wishlist_count": wishlist_count
        })
    except psycopg2.Error:
        return api_database_error()


# ==========================================
# CHECKOUT & ORDER APIS
# ==========================================

@app.post("/api/checkout")
def checkout():
    """Execute checkout transaction for current cart or direct item."""
    data = request.get_json(silent=True) or {}
    direct_asin = data.get("asin")
    direct_units = data.get("ordered_units", 1)

    shipping_name = data.get("shipping_name")
    shipping_address = data.get("shipping_address")
    shipping_city = data.get("shipping_city")
    shipping_postal_code = data.get("shipping_postal_code")
    payment_method = data.get("payment_method", "Amazon Pay")
    delivery_speed = data.get("delivery_speed", "FREE Two-Day Shipping")

    try:
        with database_connection() as conn:
            with conn.cursor() as cur:
                cust_id = get_current_customer_id(cur)
                customer = get_customer_info(cur, cust_id)

                shipping_name = shipping_name or customer.get("name", "Amazon Customer")
                shipping_address = shipping_address or customer.get("shipping_address", "410 Terry Ave N")
                shipping_city = shipping_city or customer.get("city", "Seattle")
                shipping_postal_code = shipping_postal_code or customer.get("postal_code", "98109")

                # Determine checkout items
                checkout_items = []
                if direct_asin:
                    cur.execute("SELECT standard_price, product_title FROM catalog.dim_products WHERE asin = %s", (direct_asin,))
                    p_row = cur.fetchone()
                    if not p_row:
                        return api_error("Product not found", 404)
                    checkout_items.append({
                        "asin": direct_asin,
                        "units": int(direct_units),
                        "price": float(p_row[0]),
                        "title": p_row[1]
                    })
                else:
                    cur.execute("""
                        SELECT c.asin, c.quantity, p.standard_price, p.product_title
                        FROM customers.cart_items c
                        JOIN catalog.dim_products p ON p.asin = c.asin
                        WHERE c.customer_id = %s AND c.is_saved_for_later = FALSE
                    """, (cust_id,))
                    rows = cur.fetchall()
                    if not rows:
                        return api_error("Your cart is empty", 400)
                    for r in rows:
                        checkout_items.append({
                            "asin": r[0],
                            "units": r[1],
                            "price": float(r[2]),
                            "title": r[3]
                        })

                # Verify and decrement inventory for each item
                for item in checkout_items:
                    cur.execute("""
                        SELECT snapshot_date, fulfillment_center_id, units_in_stock
                        FROM retail_inventory.fact_fba_inventory_daily
                        WHERE asin = %s
                          AND snapshot_date = (
                              SELECT MAX(inventory.snapshot_date)
                              FROM retail_inventory.fact_fba_inventory_daily inventory
                              WHERE inventory.asin = %s
                          )
                        FOR UPDATE
                    """, (item["asin"], item["asin"]))
                    inv_rows = cur.fetchall()
                    total_available = sum(r[2] for r in inv_rows)

                    if total_available < item["units"]:
                        return api_error(f"Insufficient stock for '{item['title']}'. Only {total_available} left.", 409)

                    # Decrement inventory
                    remaining_to_deduct = item["units"]
                    for snapshot_date, fc_id, stock in inv_rows:
                        deduct = min(stock, remaining_to_deduct)
                        if deduct > 0:
                            cur.execute("""
                                UPDATE retail_inventory.fact_fba_inventory_daily
                                SET units_in_stock = units_in_stock - %s,
                                    out_of_stock_flag = (units_in_stock - %s <= 0)
                                WHERE snapshot_date = %s AND asin = %s AND fulfillment_center_id = %s
                            """, (deduct, deduct, snapshot_date, item["asin"], fc_id))
                            remaining_to_deduct -= deduct
                        if remaining_to_deduct == 0:
                            break

                # Calculate total
                items_total = sum(i["price"] * i["units"] for i in checkout_items)
                shipping_cost = 4.99 if "One-Day" in delivery_speed else 0.0
                tax = round(items_total * 0.08, 2)
                grand_total = round(items_total + shipping_cost + tax, 2)

                delivery_days = 1 if "One-Day" in delivery_speed else 2
                delivery_date = date.today() + timedelta(days=delivery_days)
                tracking_number = f"AMZ-{random.randint(1000000, 9999999)}"

                # Create Order
                cur.execute("""
                    INSERT INTO retail_sales.fact_orders
                        (customer_id, payment_method, order_status, shipping_name,
                         shipping_address, shipping_city, shipping_postal_code,
                         total_amount, delivery_estimate_date, tracking_number)
                    VALUES (%s, %s, 'Ordered', %s, %s, %s, %s, %s, %s, %s)
                    RETURNING order_id, order_timestamp
                """, (
                    cust_id,
                    payment_method,
                    shipping_name,
                    shipping_address,
                    shipping_city,
                    shipping_postal_code,
                    grand_total,
                    delivery_date,
                    tracking_number
                ))
                order_row = cur.fetchone()
                order_id = str(order_row[0])
                order_timestamp = order_row[1]

                # Insert Order Items
                for item in checkout_items:
                    cur.execute("""
                        INSERT INTO retail_sales.fact_order_items
                            (order_id, asin, ordered_units, item_price, net_revenue)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (order_id, item["asin"], item["units"], item["price"], item["price"] * item["units"]))

                # Clear checked-out items from cart
                if direct_asin:
                    cur.execute("""
                        DELETE FROM customers.cart_items
                        WHERE customer_id = %s AND asin = %s AND is_saved_for_later = FALSE
                    """, (cust_id, direct_asin))
                else:
                    cur.execute("""
                        DELETE FROM customers.cart_items
                        WHERE customer_id = %s AND is_saved_for_later = FALSE
                    """, (cust_id,))

            conn.commit()

        return jsonify({
            "message": "Order placed successfully!",
            "order_id": order_id,
            "tracking_number": tracking_number,
            "order_date": order_timestamp.strftime("%B %d, %Y"),
            "delivery_date": delivery_date.strftime("%A, %B %d"),
            "total_amount": grand_total,
            "items_count": sum(i["units"] for i in checkout_items),
            "shipping_name": shipping_name,
            "shipping_address": f"{shipping_address}, {shipping_city}, {shipping_postal_code}",
            "payment_method": payment_method
        }), 201
    except psycopg2.Error:
        return api_database_error()


@app.get("/api/orders")
def get_orders():
    """Retrieve full customer order history with status tracking and items."""
    try:
        with database_connection() as conn:
            with conn.cursor() as cur:
                cust_id = get_current_customer_id(cur)
                cur.execute("""
                    SELECT o.order_id, o.order_timestamp, o.payment_method, o.order_status,
                           o.shipping_name, o.shipping_address, o.shipping_city, o.shipping_postal_code,
                           o.total_amount, o.delivery_estimate_date, o.tracking_number
                    FROM retail_sales.fact_orders o
                    WHERE o.customer_id = %s
                    ORDER BY o.order_timestamp DESC
                """, (cust_id,))
                order_rows = cur.fetchall()

                orders = []
                for o in order_rows:
                    oid = str(o[0])
                    otime = o[1]
                    # Fetch items for this order
                    cur.execute("""
                        SELECT oi.asin, oi.ordered_units, oi.item_price, oi.net_revenue,
                               p.product_title, p.brand, p.image_url
                        FROM retail_sales.fact_order_items oi
                        JOIN catalog.dim_products p ON p.asin = oi.asin
                        WHERE oi.order_id = %s
                    """, (oid,))
                    item_rows = cur.fetchall()
                    items = [
                        {
                            "asin": ir[0],
                            "units": ir[1],
                            "price": float(ir[2]),
                            "net_revenue": float(ir[3]),
                            "title": ir[4],
                            "brand": ir[5],
                            "image_url": ir[6]
                        }
                        for ir in item_rows
                    ]

                    # Simulate realistic order tracking progress based on time
                    days_ago = (datetime.now(otime.tzinfo) - otime).days if otime else 0
                    status = o[3]
                    if status not in ["Cancelled"]:
                        if days_ago >= 3:
                            status = "Delivered"
                        elif days_ago >= 2:
                            status = "Out for Delivery"
                        elif days_ago >= 1:
                            status = "Shipped"
                        else:
                            status = "Ordered"

                    orders.append({
                        "order_id": oid,
                        "order_date": otime.strftime("%B %d, %Y") if otime else "Recent",
                        "payment_method": o[2],
                        "order_status": status,
                        "shipping_name": o[4] or "Amazon Customer",
                        "shipping_address": f"{o[5]}, {o[6]}, {o[7]}",
                        "total_amount": float(o[8]) if o[8] else 0.0,
                        "delivery_date": o[9].strftime("%B %d, %Y") if o[9] else "Within 2 days",
                        "tracking_number": o[10] or f"AMZ-{oid[:8]}",
                        "items": items,
                        "can_cancel": status == "Ordered"
                    })

        return jsonify({"orders": orders, "count": len(orders)})
    except psycopg2.Error:
        return api_database_error()


@app.post("/api/orders/<order_id>/cancel")
def cancel_order(order_id: str):
    """Cancel an order and return units to stock."""
    try:
        with database_connection() as conn:
            with conn.cursor() as cur:
                cust_id = get_current_customer_id(cur)
                cur.execute("""
                    SELECT order_status FROM retail_sales.fact_orders
                    WHERE order_id = %s AND customer_id = %s
                """, (order_id, cust_id))
                row = cur.fetchone()
                if not row:
                    return api_error("Order not found", 404)
                if row[0] == "Cancelled":
                    return api_error("Order already cancelled", 400)

                # Fetch items to restore stock
                cur.execute("""
                    SELECT asin, ordered_units FROM retail_sales.fact_order_items
                    WHERE order_id = %s
                """, (order_id,))
                items = cur.fetchall()

                for asin, units in items:
                    cur.execute("""
                        UPDATE retail_inventory.fact_fba_inventory_daily
                        SET units_in_stock = units_in_stock + %s,
                            out_of_stock_flag = FALSE
                        WHERE asin = %s
                          AND snapshot_date = (
                              SELECT MAX(inventory.snapshot_date)
                              FROM retail_inventory.fact_fba_inventory_daily inventory
                              WHERE inventory.asin = %s
                          )
                    """, (units, asin, asin))

                cur.execute("""
                    UPDATE retail_sales.fact_orders
                    SET order_status = 'Cancelled'
                    WHERE order_id = %s
                """, (order_id,))

            conn.commit()

        return jsonify({"message": f"Order {order_id} cancelled successfully and refunded."})
    except psycopg2.Error:
        return api_database_error()


# ==========================================
# CUSTOMER REVIEWS API
# ==========================================

@app.post("/api/products/<asin>/reviews")
def add_review(asin: str):
    """Submit a verified customer review and update product avg rating."""
    data = request.get_json(silent=True) or {}
    rating = int(data.get("rating", 5))
    title = data.get("title", "").strip()
    text = data.get("text", "").strip()

    if not 1 <= rating <= 5:
        return api_error("Rating must be between 1 and 5")
    if not title or not text:
        return api_error("Review headline and text are required")

    try:
        with database_connection() as conn:
            with conn.cursor() as cur:
                cust_id = get_current_customer_id(cur)
                customer = get_customer_info(cur, cust_id)
                author_name = customer.get("name", "Amazon Customer")

                cur.execute("""
                    INSERT INTO catalog.dim_reviews (asin, customer_id, customer_name, rating, review_title, review_text)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING review_id, created_at
                """, (asin, cust_id, author_name, rating, title, text))
                new_rev = cur.fetchone()

                # Recompute product average rating and count
                cur.execute("""
                    SELECT ROUND(AVG(rating)::numeric, 1), COUNT(*)
                    FROM catalog.dim_reviews
                    WHERE asin = %s
                """, (asin,))
                avg_r, count_r = cur.fetchone()

                cur.execute("""
                    UPDATE catalog.dim_products
                    SET rating = %s, rating_count = %s
                    WHERE asin = %s
                """, (avg_r, count_r, asin))

            conn.commit()

        return jsonify({
            "message": "Thank you for sharing your review!",
            "review": {
                "review_id": new_rev[0],
                "customer_name": author_name,
                "rating": rating,
                "title": title,
                "text": text,
                "date": new_rev[1].strftime("%B %d, %Y")
            },
            "new_rating": float(avg_r),
            "new_count": count_r
        }), 201
    except psycopg2.Error:
        return api_database_error()


# ==========================================
# AUTHENTICATION & PROFILE APIS
# ==========================================

@app.get("/api/auth/me")
def get_me():
    """Get current active customer profile."""
    try:
        with database_connection() as conn:
            with conn.cursor() as cur:
                cust_id = get_current_customer_id(cur)
                info = get_customer_info(cur, cust_id)
        return jsonify(info)
    except psycopg2.Error:
        return api_database_error()


@app.post("/api/auth/login")
def login():
    """Log in by email and password."""
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return api_error("Email and password required")

    try:
        with database_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT customer_id, password_hash, name FROM customers.dim_customers
                    WHERE LOWER(email) = %s
                """, (email,))
                row = cur.fetchone()
                if not row or not row[1] or not check_password_hash(row[1], password):
                    return api_error("Invalid email or password", 401)

                session["customer_id"] = row[0]
                user_info = get_customer_info(cur, row[0])

        return jsonify({"message": f"Welcome back, {user_info['name']}!", "customer": user_info})
    except psycopg2.Error:
        return api_database_error()


@app.post("/api/auth/register")
def register():
    """Create a new Amazon account."""
    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip() or "Amazon Customer"
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    address = data.get("shipping_address", "410 Terry Ave N")
    city = data.get("city", "Seattle")
    postal_code = data.get("postal_code", "98109")

    if not email or "@" not in email:
        return api_error("Valid email required")
    if not password or len(password) < 6:
        return api_error("Password must be at least 6 characters")

    try:
        with database_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT customer_id FROM customers.dim_customers WHERE LOWER(email) = %s", (email,))
                if cur.fetchone():
                    return api_error("An account with this email already exists", 409)

                pwd_hash = generate_password_hash(password)
                cur.execute("""
                    INSERT INTO customers.dim_customers
                        (name, email, password_hash, shipping_address, city, postal_code, signup_date)
                    VALUES (%s, %s, %s, %s, %s, %s, CURRENT_DATE)
                    RETURNING customer_id
                """, (name, email, pwd_hash, address, city, postal_code))
                new_id = cur.fetchone()[0]
                session["customer_id"] = new_id
                user_info = get_customer_info(cur, new_id)

            conn.commit()

        return jsonify({"message": f"Account created for {name}!", "customer": user_info}), 201
    except psycopg2.Error:
        return api_database_error()


@app.post("/api/auth/demo")
def switch_demo_user():
    """One-click switch to the demo customer account."""
    try:
        with database_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT customer_id FROM customers.dim_customers WHERE email = %s", (DEMO_CUSTOMER_EMAIL,))
                row = cur.fetchone()
                if row:
                    session["customer_id"] = row[0]
                    user_info = get_customer_info(cur, row[0])
                else:
                    cid = get_current_customer_id(cur)
                    user_info = get_customer_info(cur, cid)
        return jsonify({"message": "Switched to Demo Account", "customer": user_info})
    except psycopg2.Error:
        return api_database_error()


@app.post("/api/auth/logout")
def logout():
    """Clear active customer session."""
    session.pop("customer_id", None)
    return jsonify({"message": "Signed out successfully"})


@app.post("/api/customer/address")
def update_delivery_address():
    """Update delivery destination city and postal code (syncs with navbar)."""
    data = request.get_json(silent=True) or {}
    city = data.get("city", "Seattle").strip()
    postal_code = data.get("postal_code", "98109").strip()
    shipping_address = data.get("shipping_address")

    try:
        with database_connection() as conn:
            with conn.cursor() as cur:
                cust_id = get_current_customer_id(cur)
                if shipping_address:
                    cur.execute("""
                        UPDATE customers.dim_customers
                        SET city = %s, postal_code = %s, shipping_address = %s
                        WHERE customer_id = %s
                    """, (city, postal_code, shipping_address, cust_id))
                else:
                    cur.execute("""
                        UPDATE customers.dim_customers
                        SET city = %s, postal_code = %s
                        WHERE customer_id = %s
                    """, (city, postal_code, cust_id))
            conn.commit()

        return jsonify({
            "message": "Delivery location updated",
            "city": city,
            "postal_code": postal_code
        })
    except psycopg2.Error:
        return api_database_error()


# ==========================================
# TRAFFIC / GLANCE VIEWS API
# ==========================================

@app.post("/api/view-product")
def view_product():
    """Record glance view into retail_traffic for analytics."""
    payload = request.get_json(silent=True) or {}
    asin = payload.get("asin")
    device_type = payload.get("device_type", "desktop")

    if not asin:
        return api_error("asin is required")

    try:
        with database_connection() as conn:
            with conn.cursor() as cur:
                cust_id = get_current_customer_id(cur)
                cur.execute("""
                    SELECT COALESCE(SUM(units_in_stock), 0)
                    FROM retail_inventory.fact_fba_inventory_daily
                    WHERE asin = %s
                      AND snapshot_date = (
                          SELECT MAX(inventory.snapshot_date)
                          FROM retail_inventory.fact_fba_inventory_daily inventory
                          WHERE inventory.asin = %s
                      )
                """, (asin, asin))
                row = cur.fetchone()
                in_stock = (row[0] > 0) if row else False
                delivery_days = 1 if in_stock else 5

                cur.execute("""
                    INSERT INTO retail_traffic.fact_glance_views
                        (asin, customer_id, device_type, is_buy_box_winner, estimated_delivery_days)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING view_id
                """, (asin, cust_id, device_type[:20], in_stock, delivery_days))
                view_id = str(cur.fetchone()[0])
            conn.commit()

        return jsonify({
            "view_id": view_id,
            "asin": asin,
            "is_buy_box_winner": in_stock,
            "estimated_delivery_days": delivery_days
        }), 201
    except psycopg2.Error:
        return api_database_error()


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)
