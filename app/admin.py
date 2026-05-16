from fastapi import APIRouter
import sqlite3

router = APIRouter()

DB_NAME = "shirleys_customers.db"


def get_admin_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


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
    }