from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, EmailStr
import sqlite3
from datetime import datetime
import os

from app.email_service import (
    send_customer_welcome_email,
    send_internal_new_customer_email,
    build_customer_welcome_whatsapp_url,
    build_internal_new_customer_whatsapp_url,
)

router = APIRouter()

DB_NAME = "shirleys_customers.db"
ADMIN_CUSTOMERS_TOKEN = os.getenv("ADMIN_CUSTOMERS_TOKEN", "")


class CustomerRegisterRequest(BaseModel):
    name: str
    email: EmailStr
    whatsapp: str


def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


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

    conn = get_db_connection()
    cursor = conn.cursor()

    customers = cursor.execute(
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
    ).fetchall()

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
    conn = get_db_connection()
    cursor = conn.cursor()

    existing_customer = cursor.execute(
        """
        SELECT * FROM customers
        WHERE email = ?
        """,
        (payload.email,),
    ).fetchone()

    if existing_customer:
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
        VALUES (?, ?, ?, ?, ?, ?)
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
    conn = get_db_connection()
    cursor = conn.cursor()

    customer = cursor.execute(
        """
        SELECT *
        FROM customers
        WHERE code = ?
        """,
        (customer_code,),
    ).fetchone()

    if not customer:
        conn.close()
        raise HTTPException(
            status_code=404,
            detail="Cliente no encontrado.",
        )

    purchases = cursor.execute(
        """
        SELECT
            invoice_number,
            amount,
            points_earned,
            created_at
        FROM purchases
        WHERE customer_code = ?
        ORDER BY created_at DESC
        """,
        (customer_code,),
    ).fetchall()

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
                "amount": purchase["amount"],
                "points_earned": purchase["points_earned"],
                "created_at": purchase["created_at"],
            }
            for purchase in purchases
        ],
    }