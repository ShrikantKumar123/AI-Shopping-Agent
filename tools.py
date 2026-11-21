import sqlite3
from typing import Optional

from langchain_core.tools import tool

from reviews_api import get_ratings_for_products
from setup_db import DB_PATH




def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS cart_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cart_id TEXT NOT NULL DEFAULT 'default',
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL CHECK(quantity > 0),
            added_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(cart_id, product_id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        );

        CREATE TABLE IF NOT EXISTS customer_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_ref TEXT UNIQUE,
            status TEXT NOT NULL DEFAULT 'PENDING',
            total_amount REAL NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            confirmed_at TEXT,
            cancelled_at TEXT
        );

        CREATE TABLE IF NOT EXISTS customer_order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            product_name TEXT NOT NULL,
            unit_price REAL NOT NULL,
            quantity INTEGER NOT NULL,
            subtotal REAL NOT NULL,
            FOREIGN KEY (order_id) REFERENCES customer_orders(id)
        );
    """)

    return conn


@tool
def search_products(
    keyword: Optional[str] = None,
    category: Optional[str] = None,
    max_price: Optional[float] = None,
    min_price: Optional[float] = None,
    organic_only: bool = False,
    min_rating: Optional[float] = None,
) -> list[dict]:
    """Search the store catalog.

    Args:
        keyword: Product type to look for, matched against product name and category
            (e.g. "honey", "almond", "coffee"). Do not include words like "organic" here.
        category: Exact category. One of: honey, oil, nuts, seeds, grains, tea, coffee,
            snacks, dairy-alt.
        max_price: Maximum price in USD (inclusive).
        min_price: Minimum price in USD (inclusive).
        organic_only: True to return only organic products.
        min_rating: Minimum average customer rating (0-5), inclusive.

    Returns products sorted by rating (highest first), each with id, name, category,
    price, description, is_organic, average_rating and review_count.
    """
    sql = "SELECT id, name, category, price, description, is_organic FROM products WHERE 1=1"
    params: list = []
    if keyword:
        sql += " AND (name LIKE ? OR category LIKE ?)"
        params += [f"%{keyword}%", f"%{keyword}%"]
    if category:
        sql += " AND category = ?"
        params.append(category.lower())
    if max_price is not None:
        sql += " AND price <= ?"
        params.append(max_price)
    if min_price is not None:
        sql += " AND price >= ?"
        params.append(min_price)
    if organic_only:
        sql += " AND is_organic = 1"

    with _connect() as conn:
        products = [dict(r) for r in conn.execute(sql, params).fetchall()]

    ratings = {r["product_id"]: r for r in get_ratings_for_products([p["id"] for p in products])}
    results = []
    for p in products:
        r = ratings[p["id"]]
        p["is_organic"] = bool(p["is_organic"])
        p["average_rating"] = r["average_rating"]
        p["review_count"] = r["review_count"]
        if min_rating is None or p["average_rating"] >= min_rating:
            results.append(p)

    results.sort(key=lambda p: (-p["average_rating"], p["price"]))
    return results


@tool
def place_order(product_id: int) -> dict:
    """Place an order for one product by its product id. Only call this when the user
    has clearly asked to buy/order a specific product."""
    with _connect() as conn:
        row = conn.execute("SELECT id, name, price FROM products WHERE id = ?", (product_id,)).fetchone()
        if row is None:
            return {"success": False, "error": f"No product with id {product_id}"}
        cur = conn.execute(
            "INSERT INTO orders (product_id, product_name, price) VALUES (?, ?, ?)",
            (row["id"], row["name"], row["price"]),
        )
        order = conn.execute("SELECT * FROM orders WHERE id = ?", (cur.lastrowid,)).fetchone()
    return {"success": True, "order": dict(order)}


@tool
def add_to_cart(product_id: int, quantity: int = 1) -> dict:
    """Add a product to the shopping cart or increase its quantity.

    Args:
        product_id: Valid product ID from search_products.
        quantity: Number of units to add. Must be positive.
    """
    if isinstance(product_id, bool) or product_id <= 0:
        return {"success": False, "error": "Invalid product ID."}

    if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0:
        return {"success": False, "error": "Quantity must be a positive integer."}

    with _connect() as conn:
        product = conn.execute(
            "SELECT id, name, price FROM products WHERE id = ?",
            (product_id,)
        ).fetchone()

        if product is None:
            return {"success": False, "error": "Product not found."}

        conn.execute("""
            INSERT INTO cart_items (product_id, quantity)
            VALUES (?, ?)
            ON CONFLICT(cart_id, product_id)
            DO UPDATE SET quantity = quantity + excluded.quantity
        """, (product_id, quantity))

        item = conn.execute("""
            SELECT quantity FROM cart_items
            WHERE cart_id = 'default' AND product_id = ?
        """, (product_id,)).fetchone()

    return {
        "success": True,
        "message": "Product added to cart.",
        "product_name": product["name"],
        "quantity": item["quantity"],
        "unit_price": product["price"],
        "subtotal": round(product["price"] * item["quantity"], 2)
    }



@tool
def view_cart() -> dict:
    """Display all items in the shopping cart with quantities and total price."""

    with _connect() as conn:
        rows = conn.execute("""
            SELECT
                p.id AS product_id,
                p.name,
                p.price,
                c.quantity,
                ROUND(p.price * c.quantity, 2) AS subtotal
            FROM cart_items c
            JOIN products p ON p.id = c.product_id
            WHERE c.cart_id = 'default'
            ORDER BY c.added_at DESC
        """).fetchall()

    items = [dict(row) for row in rows]

    total = round(sum(item["subtotal"] for item in items), 2)
    total_quantity = sum(item["quantity"] for item in items)

    return {
        "success": True,
        "items": items,
        "total_items": len(items),
        "total_quantity": total_quantity,
        "total_amount": total
    }



@tool
def update_cart_quantity(product_id: int, quantity: int) -> dict:
    """Set the exact quantity of an existing cart item.

    Args:
        product_id: Product ID in the cart.
        quantity: New quantity. Must be positive.
    """

    if isinstance(product_id, bool) or product_id <= 0:
        return {"success": False, "error": "Invalid product ID."}

    if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0:
        return {"success": False, "error": "Quantity must be a positive integer."}

    with _connect() as conn:
        cursor = conn.execute("""
            UPDATE cart_items
            SET quantity = ?
            WHERE cart_id = 'default' AND product_id = ?
        """, (quantity, product_id))

        if cursor.rowcount == 0:
            return {"success": False, "error": "Product not found in cart."}

    return {
        "success": True,
        "message": "Cart quantity updated.",
        "product_id": product_id,
        "quantity": quantity
    }




@tool
def remove_from_cart(product_id: int) -> dict:
    """Remove a product completely from the shopping cart.

    Args:
        product_id: Product ID to remove.
    """

    if isinstance(product_id, bool) or product_id <= 0:
        return {"success": False, "error": "Invalid product ID."}

    with _connect() as conn:
        cursor = conn.execute("""
            DELETE FROM cart_items
            WHERE cart_id = 'default' AND product_id = ?
        """, (product_id,))

    if cursor.rowcount == 0:
        return {"success": False, "error": "Product not found in cart."}

    return {
        "success": True,
        "message": "Product removed from cart.",
        "product_id": product_id
    }



@tool
def compare_products(product_ids: list[int]) -> dict:
    """Compare two or more products using their IDs.

    Args:
        product_ids: List of product IDs returned by search_products.
                     Example: [1, 5, 7]

    Returns product details, prices, ratings, review counts,
    cheapest product and highest-rated product.
    """
    # Remove duplicate IDs while preserving order
    product_ids = list(dict.fromkeys(product_ids))

    if len(product_ids) < 2:
        return {
            "success": False,
            "error": "Please provide at least two product IDs to compare."
        }

    if len(product_ids) > 5:
        return {
            "success": False,
            "error": "You can compare a maximum of five products at a time."
        }

    if any(not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0
           for pid in product_ids):
        return {
            "success": False,
            "error": "All product IDs must be positive integers."
        }

    placeholders = ",".join("?" for _ in product_ids)

    sql = f"""
        SELECT id, name, category, price, description, is_organic
        FROM products
        WHERE id IN ({placeholders})
    """

    with _connect() as conn:
        rows = conn.execute(sql, product_ids).fetchall()

    products_by_id = {row["id"]: dict(row) for row in rows}

    missing_ids = [
        pid for pid in product_ids
        if pid not in products_by_id
    ]

    if missing_ids:
        return {
            "success": False,
            "error": f"Products not found: {missing_ids}"
        }

    ratings = {
        item["product_id"]: item
        for item in get_ratings_for_products(product_ids)
    }

    products = []

    for pid in product_ids:
        product = products_by_id[pid]
        rating = ratings[pid]

        product["is_organic"] = bool(product["is_organic"])
        product["average_rating"] = rating["average_rating"]
        product["review_count"] = rating["review_count"]

        products.append(product)

    cheapest = min(products, key=lambda p: p["price"])

    highest_rated = max(
        products,
        key=lambda p: p["average_rating"]
    )

    return {
        "success": True,
        "products": products,
        "comparison": {
            "cheapest_product": {
                "id": cheapest["id"],
                "name": cheapest["name"],
                "price": cheapest["price"]
            },
            "highest_rated_product": {
                "id": highest_rated["id"],
                "name": highest_rated["name"],
                "rating": highest_rated["average_rating"]
            }
        }
    }



@tool
def checkout() -> dict:
    """Create a pending checkout from all items in the shopping cart.

    The user must explicitly confirm the order using confirm_order
    before the order is placed.
    """
    with _connect() as conn:
        items = conn.execute("""
            SELECT
                p.id AS product_id,
                p.name AS product_name,
                p.price AS unit_price,
                c.quantity,
                ROUND(p.price * c.quantity, 2) AS subtotal
            FROM cart_items c
            JOIN products p ON p.id = c.product_id
            WHERE c.cart_id = 'default'
        """).fetchall()

        if not items:
            return {
                "success": False,
                "error": "Your shopping cart is empty."
            }

        total = round(sum(item["subtotal"] for item in items), 2)

        cursor = conn.execute("""
            INSERT INTO customer_orders (total_amount)
            VALUES (?)
        """, (total,))

        order_id = cursor.lastrowid
        order_ref = f"ORD-{order_id:06d}"

        conn.execute("""
            UPDATE customer_orders
            SET order_ref = ?
            WHERE id = ?
        """, (order_ref, order_id))

        for item in items:
            conn.execute("""
                INSERT INTO customer_order_items (
                    order_id,
                    product_id,
                    product_name,
                    unit_price,
                    quantity,
                    subtotal
                )
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                order_id,
                item["product_id"],
                item["product_name"],
                item["unit_price"],
                item["quantity"],
                item["subtotal"]
            ))

    return {
        "success": True,
        "message": "Checkout created. Awaiting customer confirmation.",
        "order_id": order_ref,
        "status": "PENDING",
        "items": [dict(item) for item in items],
        "total_amount": total,
        "requires_confirmation": True
    }




@tool
def confirm_order(order_id: str) -> dict:
    """Confirm a pending checkout using its order reference.

    Args:
        order_id: Order reference returned by checkout, e.g. ORD-000001.
    """
    if not isinstance(order_id, str) or not order_id.strip():
        return {"success": False, "error": "Invalid order reference."}

    order_id = order_id.strip().upper()

    with _connect() as conn:
        order = conn.execute("""
            SELECT * FROM customer_orders
            WHERE order_ref = ?
        """, (order_id,)).fetchone()

        if order is None:
            return {"success": False, "error": "Order not found."}

        if order["status"] != "PENDING":
            return {
                "success": False,
                "error": f"Order cannot be confirmed. Current status: {order['status']}."
            }

        items = conn.execute("""
            SELECT product_id, quantity
            FROM customer_order_items
            WHERE order_id = ?
        """, (order["id"],)).fetchall()

        conn.execute("""
            UPDATE customer_orders
            SET status = 'CONFIRMED',
                confirmed_at = datetime('now')
            WHERE id = ? AND status = 'PENDING'
        """, (order["id"],))

        # Remove only the cart quantities included in this checkout.
        for item in items:
            conn.execute("""
                DELETE FROM cart_items
                WHERE cart_id = 'default'
                  AND product_id = ?
                  AND quantity = ?
            """, (item["product_id"], item["quantity"]))

    return {
        "success": True,
        "message": "Order confirmed successfully.",
        "order_id": order_id,
        "status": "CONFIRMED",
        "total_amount": order["total_amount"]
    }


@tool
def get_order_history() -> dict:
    """Retrieve all previous orders with their products and statuses."""

    with _connect() as conn:
        orders = conn.execute("""
            SELECT *
            FROM customer_orders
            ORDER BY id DESC
        """).fetchall()

        result = []

        for order in orders:
            items = conn.execute("""
                SELECT
                    product_name,
                    unit_price,
                    quantity,
                    subtotal
                FROM customer_order_items
                WHERE order_id = ?
            """, (order["id"],)).fetchall()

            result.append({
                **dict(order),
                "items": [dict(item) for item in items]
            })

    return {
        "success": True,
        "total_orders": len(result),
        "orders": result
    }



@tool
def cancel_order(order_id: str) -> dict:
    """Cancel an order only if its status is PENDING.

    Args:
        order_id: Order reference, e.g. ORD-000001.
    """

    if not isinstance(order_id, str) or not order_id.strip():
        return {"success": False, "error": "Invalid order reference."}

    order_id = order_id.strip().upper()

    with _connect() as conn:
        order = conn.execute("""
            SELECT id, status
            FROM customer_orders
            WHERE order_ref = ?
        """, (order_id,)).fetchone()

        if order is None:
            return {"success": False, "error": "Order not found."}

        if order["status"] != "PENDING":
            return {
                "success": False,
                "error": "Only pending orders can be cancelled."
            }

        conn.execute("""
            UPDATE customer_orders
            SET status = 'CANCELLED',
                cancelled_at = datetime('now')
            WHERE id = ? AND status = 'PENDING'
        """, (order["id"],))

    return {
        "success": True,
        "message": "Order cancelled successfully.",
        "order_id": order_id,
        "status": "CANCELLED"
    }


TOOLS = [
    search_products,
    compare_products,
    add_to_cart,
    view_cart,
    update_cart_quantity,
    remove_from_cart,
    checkout,
    confirm_order,
    get_order_history,
    cancel_order
]
