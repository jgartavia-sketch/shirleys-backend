from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Literal
from datetime import datetime
import sqlite3
import json

router = APIRouter()

DB_NAME = "shirleys_customers.db"


def get_admin_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_whatsapp_orders_table():
    conn = get_admin_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS whatsapp_orders (
            id TEXT PRIMARY KEY,
            customer_name TEXT,
            customer_phone TEXT,
            order_type TEXT NOT NULL,
            location_text TEXT,
            items_json TEXT NOT NULL,
            food_total REAL NOT NULL,
            packaging_total REAL NOT NULL,
            total REAL NOT NULL,
            status TEXT NOT NULL,
            notes TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            confirmed_at TEXT
        )
    """)

    conn.commit()
    conn.close()


ensure_whatsapp_orders_table()


class UpdateWhatsappOrderRequest(BaseModel):
    status: Literal["pending_confirmation", "confirmed", "cancelled", "modified"]
    total: Optional[float] = None
    notes: Optional[str] = None


@router.delete("/customers")
def delete_all_customers():
    conn = get_admin_db_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM purchases")
    cursor.execute("DELETE FROM customers")

    conn.commit()
    conn.close()

    return {
        "success": True,
        "message": "Todos los clientes y compras fueron eliminados correctamente.",
    }


@router.get("/summary")
def get_admin_summary():
    conn = get_admin_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM customers")
    total_customers = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM purchases")
    total_purchases = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM purchases")
    total_sales = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COALESCE(SUM(points_earned), 0) FROM purchases")
    total_points_delivered = cursor.fetchone()[0] or 0

    average_ticket = round(total_sales / total_purchases, 2) if total_purchases > 0 else 0

    cursor.execute("""
        SELECT COUNT(*)
        FROM customers
        WHERE strftime('%Y-%m', created_at) = strftime('%Y-%m', 'now')
    """)
    new_customers_this_month = cursor.fetchone()[0] or 0

    cursor.execute("""
        SELECT
            c.code,
            c.name,
            c.email,
            c.whatsapp,
            c.points,
            COUNT(p.id) AS purchases_count,
            COALESCE(SUM(p.amount), 0) AS total_spent,
            MAX(p.created_at) AS last_purchase
        FROM customers c
        LEFT JOIN purchases p ON p.customer_code = c.code
        GROUP BY c.code, c.name, c.email, c.whatsapp, c.points
        ORDER BY total_spent DESC, purchases_count DESC
        LIMIT 10
    """)

    top_customers = [dict(row) for row in cursor.fetchall()]

    cursor.execute("""
        SELECT
            p.invoice_number,
            p.amount,
            p.points_earned,
            p.created_at,
            c.code,
            c.name,
            c.email,
            c.whatsapp
        FROM purchases p
        LEFT JOIN customers c ON c.code = p.customer_code
        ORDER BY p.created_at DESC
        LIMIT 15
    """)

    recent_purchases = [
        {
            "invoice_number": row["invoice_number"],
            "amount": row["amount"],
            "points_earned": row["points_earned"],
            "created_at": row["created_at"],
            "customer": {
                "code": row["code"],
                "name": row["name"],
                "email": row["email"],
                "whatsapp": row["whatsapp"],
            },
        }
        for row in cursor.fetchall()
    ]

    cursor.execute("SELECT COUNT(*) FROM whatsapp_orders")
    whatsapp_orders_received = cursor.fetchone()[0] or 0

    cursor.execute("""
        SELECT COUNT(*)
        FROM whatsapp_orders
        WHERE status = 'confirmed'
    """)
    whatsapp_orders_confirmed = cursor.fetchone()[0] or 0

    cursor.execute("""
        SELECT COUNT(*)
        FROM whatsapp_orders
        WHERE status = 'cancelled'
    """)
    whatsapp_orders_cancelled = cursor.fetchone()[0] or 0

    cursor.execute("""
        SELECT COALESCE(SUM(total), 0)
        FROM whatsapp_orders
        WHERE status = 'confirmed'
    """)
    whatsapp_total_confirmed = cursor.fetchone()[0] or 0

    cursor.execute("""
        SELECT COALESCE(SUM(packaging_total), 0)
        FROM whatsapp_orders
        WHERE status = 'confirmed'
    """)
    whatsapp_packaging_confirmed = cursor.fetchone()[0] or 0

    whatsapp_average_confirmed_ticket = (
        round(whatsapp_total_confirmed / whatsapp_orders_confirmed, 2)
        if whatsapp_orders_confirmed > 0
        else 0
    )

    conn.close()

    return {
        "total_customers": total_customers,
        "total_purchases": total_purchases,
        "total_sales": total_sales,
        "total_points_delivered": total_points_delivered,
        "average_ticket": average_ticket,
        "new_customers_this_month": new_customers_this_month,
        "top_customers": top_customers,
        "recent_purchases": recent_purchases,
        "whatsapp_orders_received": whatsapp_orders_received,
        "whatsapp_orders_confirmed": whatsapp_orders_confirmed,
        "whatsapp_orders_cancelled": whatsapp_orders_cancelled,
        "whatsapp_total_confirmed": whatsapp_total_confirmed,
        "whatsapp_packaging_confirmed": whatsapp_packaging_confirmed,
        "whatsapp_average_confirmed_ticket": whatsapp_average_confirmed_ticket,
    }


@router.get("/whatsapp-orders")
def list_whatsapp_orders():
    conn = get_admin_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            customer_name,
            customer_phone,
            order_type,
            location_text,
            items_json,
            food_total,
            packaging_total,
            total,
            status,
            notes,
            created_at,
            updated_at,
            confirmed_at
        FROM whatsapp_orders
        ORDER BY created_at DESC
        LIMIT 100
    """)

    orders = []

    for row in cursor.fetchall():
        order = dict(row)

        try:
            order["items"] = json.loads(order["items_json"])
        except json.JSONDecodeError:
            order["items"] = []

        del order["items_json"]
        orders.append(order)

    conn.close()

    return {
        "orders": orders
    }


@router.patch("/whatsapp-orders/{order_id}")
def update_whatsapp_order(order_id: str, data: UpdateWhatsappOrderRequest):
    conn = get_admin_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM whatsapp_orders
        WHERE id = ?
    """, (order_id,))

    existing_order = cursor.fetchone()

    if not existing_order:
        conn.close()
        raise HTTPException(status_code=404, detail="WhatsApp order not found")

    now = datetime.utcnow().isoformat()
    confirmed_at = now if data.status == "confirmed" else None

    final_total = data.total if data.total is not None else existing_order["total"]
    final_notes = data.notes if data.notes is not None else existing_order["notes"]

    cursor.execute("""
        UPDATE whatsapp_orders
        SET
            status = ?,
            total = ?,
            notes = ?,
            updated_at = ?,
            confirmed_at = ?
        WHERE id = ?
    """, (
        data.status,
        final_total,
        final_notes,
        now,
        confirmed_at,
        order_id,
    ))

    conn.commit()
    conn.close()

    return {
        "success": True,
        "message": "WhatsApp order updated successfully",
        "order_id": order_id,
        "status": data.status,
    }