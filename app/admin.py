from fastapi import APIRouter
from app.customers import get_db_connection

router = APIRouter()


@router.get("/summary")
def get_admin_summary():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM customers")
    total_customers = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM purchases")
    total_purchases = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM purchases")
    total_sales = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COALESCE(SUM(points_earned), 0) FROM purchases")
    total_points_delivered = cursor.fetchone()[0] or 0

    average_ticket = 0
    if total_purchases > 0:
        average_ticket = round(total_sales / total_purchases, 2)

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
    top_customers = [
        {
            "code": row[0],
            "name": row[1],
            "email": row[2],
            "whatsapp": row[3],
            "points": row[4],
            "purchases_count": row[5],
            "total_spent": row[6],
            "last_purchase": row[7],
        }
        for row in cursor.fetchall()
    ]

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
            "invoice_number": row[0],
            "amount": row[1],
            "points_earned": row[2],
            "created_at": row[3],
            "customer": {
                "code": row[4],
                "name": row[5],
                "email": row[6],
                "whatsapp": row[7],
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