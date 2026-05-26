from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, EmailStr
from datetime import datetime
import os
import psycopg2
import psycopg2.extras

from app.email_service import (
    send_customer_welcome_email,
    send_internal_new_customer_email,
    build_customer_welcome_whatsapp_url,
    build_internal_new_customer_whatsapp_url,
)

router = APIRouter()

DATABASE_URL = os.getenv("DATABASE_URL")
ADMIN_CUSTOMERS_TOKEN = os.getenv("ADMIN_CUSTOMERS_TOKEN", "")


class CustomerRegisterRequest(BaseModel):
    name: str
    email: EmailStr
    whatsapp: str


def get_db_connection():
    if not DATABASE_URL:
        raise HTTPException(
            status_code=500,
            detail="DATABASE_URL no está configurado en el servidor.",
        )

    return psycopg2.connect(
        DATABASE_URL,
        cursor_factory=psycopg2.extras.RealDictCursor,
    )


def ensure_customers_tables():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS customers (
            id SERIAL PRIMARY KEY,
            code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            whatsapp TEXT NOT NULL,
            points INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS purchases (
            id SERIAL PRIMARY KEY,
            customer_code TEXT NOT NULL,
            invoice_number TEXT NOT NULL,
            amount NUMERIC NOT NULL,
            points_earned INTEGER NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )

    conn.commit()
    cursor.close()
    conn.close()


def generate_customer_code():
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"SHR-{timestamp}"


def verify_admin_token(x_admin_token: str | None):
    if not ADMIN_CUSTOMERS_TOKEN:
        raise HTTPException(
            status_code=500,
            detail="ADMIN_CUSTOMERS_TOKEN no está configurado en el servidor.",
        )

    if x_admin_token != ADMIN_CUSTOMERS_TOKEN:
        raise HTTPException(
            status_code=401,
            detail="Token admin inválido.",
        )


@router.get("/admin/list")
def list_customers(x_admin_token: str | None = Header(default=None)):
    verify_admin_token(x_admin_token)
    ensure_customers_tables()

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            id,
            code,
            name,
            email,
            whatsapp,
            points,
            created_at
        FROM customers
        ORDER BY created_at DESC
        """
    )

    customers = cursor.fetchall()

    cursor.close()
    conn.close()

    return {
        "success": True,
        "total": len(customers),
        "customers": [
            {
                "id": customer["id"],
                "code": customer["code"],
                "name": customer["name"],
                "email": customer["email"],
                "whatsapp": customer["whatsapp"],
                "points": customer["points"],
                "created_at": customer["created_at"],
            }
            for customer in customers
        ],
    }


@router.post("/register")
def register_customer(payload: CustomerRegisterRequest):
    ensure_customers_tables()

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *
        FROM customers
        WHERE email = %s
        """,
        (payload.email,),
    )

    existing_customer = cursor.fetchone()

    if existing_customer:
        cursor.close()
        conn.close()
        raise HTTPException(
            status_code=409,
            detail="Este correo ya está registrado.",
        )

    customer_code = generate_customer_code()
    created_at = datetime.now().isoformat()

    cursor.execute(
        """
        INSERT INTO customers (
            code,
            name,
            email,
            whatsapp,
            points,
            created_at
        )
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (
            customer_code,
            payload.name,
            payload.email,
            payload.whatsapp,
            0,
            created_at,
        ),
    )

    conn.commit()
    cursor.close()
    conn.close()

    email_sent = send_customer_welcome_email(
        customer_name=payload.name,
        customer_email=payload.email,
        customer_code=customer_code,
    )

    internal_email_sent = send_internal_new_customer_email(
        customer_name=payload.name,
        customer_email=payload.email,
        customer_whatsapp=payload.whatsapp,
        customer_code=customer_code,
    )

    customer_whatsapp_url = build_customer_welcome_whatsapp_url(
        customer_name=payload.name,
        customer_whatsapp=payload.whatsapp,
        customer_code=customer_code,
    )

    shirleys_whatsapp_url = build_internal_new_customer_whatsapp_url(
        customer_name=payload.name,
        customer_email=payload.email,
        customer_whatsapp=payload.whatsapp,
        customer_code=customer_code,
    )

    return {
        "success": True,
        "message": "Cliente registrado correctamente.",
        "customer_code": customer_code,
        "email_sent": email_sent,
        "internal_email_sent": internal_email_sent,
        "customer_whatsapp_url": customer_whatsapp_url,
        "shirleys_whatsapp_url": shirleys_whatsapp_url,
    }


@router.get("/{customer_code}")
def get_customer(customer_code: str):
    ensure_customers_tables()

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *
        FROM customers
        WHERE code = %s
        """,
        (customer_code,),
    )

    customer = cursor.fetchone()

    if not customer:
        cursor.close()
        conn.close()
        raise HTTPException(
            status_code=404,
            detail="Cliente no encontrado.",
        )

    cursor.execute(
        """
        SELECT
            invoice_number,
            amount,
            points_earned,
            created_at
        FROM purchases
        WHERE customer_code = %s
        ORDER BY created_at DESC
        """,
        (customer_code,),
    )

    purchases = cursor.fetchall()

    cursor.close()
    conn.close()

    return {
        "customer": {
            "code": customer["code"],
            "name": customer["name"],
            "email": customer["email"],
            "whatsapp": customer["whatsapp"],
            "points": customer["points"],
            "created_at": customer["created_at"],
        },
        "purchases": [
            {
                "invoice_number": purchase["invoice_number"],
                "amount": float(purchase["amount"]),
                "points_earned": purchase["points_earned"],
                "created_at": purchase["created_at"],
            }
            for purchase in purchases
        ],
    }