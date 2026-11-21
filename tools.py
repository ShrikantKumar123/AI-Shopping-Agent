
"""Shopping tools for the AI Shopping Agent.

Cart and order data are isolated by authenticated user.
The user ID is supplied by the application through a ContextVar,
not collected from the LLM.
"""

import os
import sqlite3
from contextvars import ContextVar
from typing import Optional

from langchain_core.tools import tool

from reviews_api import get_ratings_for_products
from setup_db import DB_PATH


# -------------------------------------------------------------------
# Authenticated user context
# -------------------------------------------------------------------

_current_user_id = ContextVar("current_user_id", default=None)


def set_current_user_id(user_id: int):
    """Set the authenticated user for the current agent execution."""
    if isinstance(user_id, bool) or not isinstance(user_id, int) or user_id <= 0:
        raise ValueError("A valid authenticated user ID is required.")

    return _current_user_id.set(user_id)


def reset_current_user_id(token):
    """Restore the previous user context after agent execution."""
    _current_user_id.reset(token)


def _get_current_user_id() -> int:
    """Return the authenticated user ID or reject the operation."""
    user_id = _current_user_id.get()

    if isinstance(user_id, bool) or not isinstance(user_id, int) or user_id <= 0:
        raise PermissionError(
            "User authentication is required to access cart and order features."
        )

    return user_id


def _get_cart_id(user_id: int) -> str:
    """Generate a separate cart ID for each user."""
    return f"user_{user_id}"


# -------------------------------------------------------------------
# Database connection and schema
# -------------------------------------------------------------------

def _connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)

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
            cancelled_at TEXT,
            user_id INTEGER
        );

        CREATE TABLE IF NOT EXISTS customer_order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            product_name TEXT NOT NULL,
            unit_price REAL NOT NULL,
            quantity INTEGER NOT NULL,
            subtotal REAL NOT NULL,
            FOREIGN KEY (order_id)
                REFERENCES customer_orders(id)
                ON DELETE CASCADE
        );
    """)

    # Migration for databases created before user-specific orders.
    order_columns = {
        row["name"]
        for row in conn.execute(
            "PRAGMA table_info(customer_orders)"
        ).fetchall()
    }

    if "user_id" not in order_columns:
        conn.execute(
            "ALTER TABLE customer_orders ADD COLUMN user_id INTEGER"
        )

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_customer_orders_user_id
        ON customer_orders(user_id)
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_cart_items_cart_id
        ON cart_items(cart_id)
    """)

    return conn


# -------------------------------------------------------------------
# Product search
# -------------------------------------------------------------------

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
        keyword: Product type to look for, matched against product name
            and category (e.g. honey, almond, coffee).
        category: Exact category.
        max_price: Maximum price in USD (inclusive).
        min_price: Minimum price in USD (inclusive).
        organic_only: True to return only organic products.
        min_rating: Minimum average customer rating (0-5), inclusive.

    Returns products sorted by rating, with product details and ratings.
    """

    if min_price is not None and max_price is not None:
        if min_price > max_price:
            return []

    sql = """
        SELECT id, name, category, price, description, is_organic
        FROM products
        WHERE 1=1
    """

    params = []

    if keyword:
        sql += " AND (name LIKE ? OR category LIKE ?)"
        params.extend([f"%{keyword}%", f"%{keyword}%"])

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
        products = [
            dict(row)
            for row in conn.execute(sql, params).fetchall()
        ]

    if not products:
        return []

    ratings = {
        rating["product_id"]: rating
        for rating in get_ratings_for_products(
            [product["id"] for product in products]
        )
    }

    results = []

    for product in products:
        rating = ratings.get(product["id"], {
            "average_rating": 0,
            "review_count": 0
        })

        product["is_organic"] = bool(product["is_organic"])
        product["average_rating"] = rating["average_rating"]
        product["review_count"] = rating["review_count"]

        if (
            min_rating is None
            or product["average_rating"] >= min_rating
        ):
            results.append(product)

    results.sort(
        key=lambda product: (
            -product["average_rating"],
            product["price"]
        )
    )

    return results


# -------------------------------------------------------------------
# Legacy order function
# -------------------------------------------------------------------

@tool
def place_order(product_id: int) -> dict:
    """Legacy single-product order function.

    This function is not registered in TOOLS.
    Use add_to_cart, checkout and confirm_order for the current flow.
    """

    if isinstance(product_id, bool) or not isinstance(product_id, int):
        return {"success": False, "error": "Invalid product ID."}

    if product_id <= 0:
        return {"success": False, "error": "Invalid product ID."}

    with _connect() as conn:
        product = conn.execute(
            """
            SELECT id, name, price
            FROM products
            WHERE id = ?
            """,
            (product_id,)
        ).fetchone()

        if product is None:
            return {
                "success": False,
                "error": f"No product with ID {product_id}."
            }

        cursor = conn.execute(
            """
            INSERT INTO orders (product_id, product_name, price)
            VALUES (?, ?, ?)
            """,
            (product["id"], product["name"], product["price"])
        )

        order = conn.execute(
            "SELECT * FROM orders WHERE id = ?",
            (cursor.lastrowid,)
        ).fetchone()

    return {
        "success": True,
        "order": dict(order)
    }


# -------------------------------------------------------------------
# Shopping cart
# -------------------------------------------------------------------

@tool
def add_to_cart(product_id: int, quantity: int = 1) -> dict:
    """Add a product to the authenticated user's shopping cart.

    Args:
        product_id: Valid product ID returned by search_products.
        quantity: Number of units to add. Must be positive.
    """

    user_id = _get_current_user_id()
    cart_id = _get_cart_id(user_id)

    if isinstance(product_id, bool) or not isinstance(product_id, int):
        return {"success": False, "error": "Invalid product ID."}

    if product_id <= 0:
        return {"success": False, "error": "Invalid product ID."}

    if isinstance(quantity, bool) or not isinstance(quantity, int):
        return {
            "success": False,
            "error": "Quantity must be a positive integer."
        }

    if quantity <= 0:
        return {
            "success": False,
            "error": "Quantity must be a positive integer."
        }

    with _connect() as conn:
        product = conn.execute(
            """
            SELECT id, name, price
            FROM products
            WHERE id = ?
            """,
            (product_id,)
        ).fetchone()

        if product is None:
            return {"success": False, "error": "Product not found."}

        conn.execute(
            """
            INSERT INTO cart_items (
                cart_id,
                product_id,
                quantity
            )
            VALUES (?, ?, ?)
            ON CONFLICT(cart_id, product_id)
            DO UPDATE SET
                quantity = cart_items.quantity + excluded.quantity
            """,
            (cart_id, product_id, quantity)
        )

        item = conn.execute(
            """
            SELECT quantity
            FROM cart_items
            WHERE cart_id = ? AND product_id = ?
            """,
            (cart_id, product_id)
        ).fetchone()

    return {
        "success": True,
        "message": "Product added to cart.",
        "product_name": product["name"],
        "quantity": item["quantity"],
        "unit_price": product["price"],
        "subtotal": round(
            product["price"] * item["quantity"],
            2
        )
    }


@tool
def view_cart() -> dict:
    """Display the authenticated user's shopping cart."""

    user_id = _get_current_user_id()
    cart_id = _get_cart_id(user_id)

    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT
                p.id AS product_id,
                p.name,
                p.price,
                c.quantity,
                ROUND(p.price * c.quantity, 2) AS subtotal
            FROM cart_items c
            JOIN products p ON p.id = c.product_id
            WHERE c.cart_id = ?
            ORDER BY c.added_at DESC
            """,
            (cart_id,)
        ).fetchall()

    items = [dict(row) for row in rows]

    total = round(
        sum(item["subtotal"] for item in items),
        2
    )

    total_quantity = sum(
        item["quantity"] for item in items
    )

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
        product_id: Product ID in the authenticated user's cart.
        quantity: New quantity. Must be positive.
    """

    user_id = _get_current_user_id()
    cart_id = _get_cart_id(user_id)

    if isinstance(product_id, bool) or not isinstance(product_id, int):
        return {"success": False, "error": "Invalid product ID."}

    if product_id <= 0:
        return {"success": False, "error": "Invalid product ID."}

    if isinstance(quantity, bool) or not isinstance(quantity, int):
        return {
            "success": False,
            "error": "Quantity must be a positive integer."
        }

    if quantity <= 0:
        return {
            "success": False,
            "error": "Quantity must be a positive integer."
        }

    with _connect() as conn:
        cursor = conn.execute(
            """
            UPDATE cart_items
            SET quantity = ?
            WHERE cart_id = ? AND product_id = ?
            """,
            (quantity, cart_id, product_id)
        )

        if cursor.rowcount == 0:
            return {
                "success": False,
                "error": "Product not found in your cart."
            }

    return {
        "success": True,
        "message": "Cart quantity updated.",
        "product_id": product_id,
        "quantity": quantity
    }


@tool
def remove_from_cart(product_id: int) -> dict:
    """Remove a product from the authenticated user's cart.

    Args:
        product_id: Product ID to remove from the user's cart.
    """

    user_id = _get_current_user_id()
    cart_id = _get_cart_id(user_id)

    if isinstance(product_id, bool) or not isinstance(product_id, int):
        return {"success": False, "error": "Invalid product ID."}

    if product_id <= 0:
        return {"success": False, "error": "Invalid product ID."}

    with _connect() as conn:
        cursor = conn.execute(
            """
            DELETE FROM cart_items
            WHERE cart_id = ? AND product_id = ?
            """,
            (cart_id, product_id)
        )

        if cursor.rowcount == 0:
            return {
                "success": False,
                "error": "Product not found in your cart."
            }

    return {
        "success": True,
        "message": "Product removed from cart.",
        "product_id": product_id
    }


# -------------------------------------------------------------------
# Product comparison
# -------------------------------------------------------------------

@tool
def compare_products(product_ids: list[int]) -> dict:
    """Compare two or more products using their IDs.

    Args:
        product_ids: List of product IDs returned by search_products.
                     Example: [1, 5, 7]

    Returns product details, prices, ratings, review counts,
    cheapest product and highest-rated product.
    """

    if not isinstance(product_ids, list):
        return {
            "success": False,
            "error": "Product IDs must be provided as a list."
        }

    if any(
        not isinstance(pid, int)
        or isinstance(pid, bool)
        or pid <= 0
        for pid in product_ids
    ):
        return {
            "success": False,
            "error": "All product IDs must be positive integers."
        }

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

    placeholders = ",".join("?" for _ in product_ids)

    sql = f"""
        SELECT
            id,
            name,
            category,
            price,
            description,
            is_organic
        FROM products
        WHERE id IN ({placeholders})
    """

    with _connect() as conn:
        rows = conn.execute(sql, product_ids).fetchall()

    products_by_id = {
        row["id"]: dict(row)
        for row in rows
    }

    missing_ids = [
        product_id
        for product_id in product_ids
        if product_id not in products_by_id
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

    for product_id in product_ids:
        product = products_by_id[product_id]
        rating = ratings.get(product_id, {
            "average_rating": 0,
            "review_count": 0
        })

        product["is_organic"] = bool(product["is_organic"])
        product["average_rating"] = rating["average_rating"]
        product["review_count"] = rating["review_count"]

        products.append(product)

    cheapest = min(
        products,
        key=lambda product: product["price"]
    )

    highest_rated = max(
        products,
        key=lambda product: product["average_rating"]
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


# -------------------------------------------------------------------
# Checkout
# -------------------------------------------------------------------

@tool
def checkout() -> dict:
    """Create a pending checkout using the authenticated user's cart.

    The customer must explicitly confirm the order using confirm_order
    before the order is confirmed.
    """

    user_id = _get_current_user_id()
    cart_id = _get_cart_id(user_id)

    with _connect() as conn:
        items = conn.execute(
            """
            SELECT
                p.id AS product_id,
                p.name AS product_name,
                p.price AS unit_price,
                c.quantity,
                ROUND(p.price * c.quantity, 2) AS subtotal
            FROM cart_items c
            JOIN products p ON p.id = c.product_id
            WHERE c.cart_id = ?
            """,
            (cart_id,)
        ).fetchall()

        if not items:
            return {
                "success": False,
                "error": "Your shopping cart is empty."
            }

        total = round(
            sum(item["subtotal"] for item in items),
            2
        )

        cursor = conn.execute(
            """
            INSERT INTO customer_orders (
                user_id,
                total_amount
            )
            VALUES (?, ?)
            """,
            (user_id, total)
        )

        order_pk = cursor.lastrowid
        order_ref = f"ORD-{order_pk:06d}"

        conn.execute(
            """
            UPDATE customer_orders
            SET order_ref = ?
            WHERE id = ? AND user_id = ?
            """,
            (order_ref, order_pk, user_id)
        )

        for item in items:
            conn.execute(
                """
                INSERT INTO customer_order_items (
                    order_id,
                    product_id,
                    product_name,
                    unit_price,
                    quantity,
                    subtotal
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    order_pk,
                    item["product_id"],
                    item["product_name"],
                    item["unit_price"],
                    item["quantity"],
                    item["subtotal"]
                )
            )

    return {
        "success": True,
        "message": "Checkout created. Awaiting customer confirmation.",
        "order_id": order_ref,
        "status": "PENDING",
        "items": [dict(item) for item in items],
        "total_amount": total,
        "requires_confirmation": True
    }


# -------------------------------------------------------------------
# Confirm order
# -------------------------------------------------------------------

@tool
def confirm_order(order_id: str) -> dict:
    """Confirm a pending order belonging to the authenticated user.

    Args:
        order_id: Order reference returned by checkout,
                  e.g. ORD-000001.
    """

    user_id = _get_current_user_id()

    if not isinstance(order_id, str) or not order_id.strip():
        return {
            "success": False,
            "error": "Invalid order reference."
        }

    order_id = order_id.strip().upper()

    with _connect() as conn:
        order = conn.execute(
            """
            SELECT *
            FROM customer_orders
            WHERE order_ref = ? AND user_id = ?
            """,
            (order_id, user_id)
        ).fetchone()

        if order is None:
            return {
                "success": False,
                "error": "Order not found."
            }

        if order["status"] != "PENDING":
            return {
                "success": False,
                "error": (
                    "Order cannot be confirmed. "
                    f"Current status: {order['status']}."
                )
            }

        items = conn.execute(
            """
            SELECT product_id, quantity
            FROM customer_order_items
            WHERE order_id = ?
            """,
            (order["id"],)
        ).fetchall()

        cursor = conn.execute(
            """
            UPDATE customer_orders
            SET status = 'CONFIRMED',
                confirmed_at = datetime('now')
            WHERE id = ?
              AND user_id = ?
              AND status = 'PENDING'
            """,
            (order["id"], user_id)
        )

        if cursor.rowcount == 0:
            return {
                "success": False,
                "error": "Order could not be confirmed. Please try again."
            }

        cart_id = _get_cart_id(user_id)

        # Remove only the quantities included in this checkout.
        # If the customer added more units after checkout, preserve them.
        for item in items:
            conn.execute(
                """
                UPDATE cart_items
                SET quantity = quantity - ?
                WHERE cart_id = ?
                  AND product_id = ?
                  AND quantity > ?
                """,
                (
                    item["quantity"],
                    cart_id,
                    item["product_id"],
                    item["quantity"]
                )
            )

            conn.execute(
                """
                DELETE FROM cart_items
                WHERE cart_id = ?
                  AND product_id = ?
                  AND quantity <= 0
                """,
                (cart_id, item["product_id"])
            )

    return {
        "success": True,
        "message": "Order confirmed successfully.",
        "order_id": order_id,
        "status": "CONFIRMED",
        "total_amount": order["total_amount"]
    }


# -------------------------------------------------------------------
# Order history
# -------------------------------------------------------------------

@tool
def get_order_history() -> dict:
    """Retrieve only the authenticated user's previous orders."""

    user_id = _get_current_user_id()

    with _connect() as conn:
        orders = conn.execute(
            """
            SELECT *
            FROM customer_orders
            WHERE user_id = ?
            ORDER BY id DESC
            """,
            (user_id,)
        ).fetchall()

        result = []

        for order in orders:
            items = conn.execute(
                """
                SELECT
                    product_name,
                    unit_price,
                    quantity,
                    subtotal
                FROM customer_order_items
                WHERE order_id = ?
                """,
                (order["id"],)
            ).fetchall()

            result.append({
                **dict(order),
                "items": [dict(item) for item in items]
            })

    return {
        "success": True,
        "total_orders": len(result),
        "orders": result
    }


# -------------------------------------------------------------------
# Cancel order
# -------------------------------------------------------------------

@tool
def cancel_order(order_id: str) -> dict:
    """Cancel a pending order belonging to the authenticated user.

    Args:
        order_id: Order reference, e.g. ORD-000001.
    """

    user_id = _get_current_user_id()

    if not isinstance(order_id, str) or not order_id.strip():
        return {
            "success": False,
            "error": "Invalid order reference."
        }

    order_id = order_id.strip().upper()

    with _connect() as conn:
        order = conn.execute(
            """
            SELECT id, status
            FROM customer_orders
            WHERE order_ref = ? AND user_id = ?
            """,
            (order_id, user_id)
        ).fetchone()

        if order is None:
            return {
                "success": False,
                "error": "Order not found."
            }

        if order["status"] != "PENDING":
            return {
                "success": False,
                "error": "Only pending orders can be cancelled."
            }

        cursor = conn.execute(
            """
            UPDATE customer_orders
            SET status = 'CANCELLED',
                cancelled_at = datetime('now')
            WHERE id = ?
              AND status = 'PENDING'
            """,
            (order["id"],)
        )

        if cursor.rowcount == 0:
            return {
                "success": False,
                "error": "Order could not be cancelled. Please try again."
            }

    return {
        "success": True,
        "message": "Order cancelled successfully.",
        "order_id": order_id,
        "status": "CANCELLED"
    }


# -------------------------------------------------------------------
# LangChain tool registration
# -------------------------------------------------------------------

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
