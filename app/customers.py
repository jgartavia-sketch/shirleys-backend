from fastapi import APIRouter, HTTPException, Header, Request
from pydantic import BaseModel, EmailStr
from datetime import datetime
from collections import defaultdict, deque
from time import time
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

RATE_LIMIT_STORE = defaultdict(deque)


class CustomerRegisterRequest(BaseModel):
    name: str
    email: EmailStr
    whatsapp: str


class PurchaseRegisterRequest(BaseModel):
    invoice_number: str
    amount: float


class PurchaseRegisterByBodyRequest(BaseModel):
    customer_code: str
    invoice_number: str
    amount: float


def get_client_ip(request: Request):
    forwarded_for = request.headers.get("x-forwarded-for")

    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    if request.client:
        return request.client.host

    return "unknown"


def check_rate_limit(
    request: Request,
    key: str,
    max_requests: int,
    window_seconds: int,
):
    client_ip = get_client_ip(request)
    rate_key = f"{key}:{client_ip}"
    now = time()
    attempts = RATE_LIMIT_STORE[rate_key]

    while attempts and now - attempts[0] > window_seconds:
        attempts.popleft()

    if len(attempts) >= max_requests:
        raise HTTPException(
            status_code=429,
            detail="Demasiadas solicitudes. Intente de nuevo en unos minutos.",
        )

    attempts.append(now)


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


def calculate_points(amount: float):
    if amount >= 15000:
        return 9
    if amount >= 10000:
        return 7
    if amount >= 5000:
        return 3
    return 0


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


def build_customer_response(customer):
    customer_code = customer["code"]

    conn = get_db_connection()
    cursor = conn.cursor()

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


def create_purchase_for_customer(customer_code: str, invoice_number: str, amount: float):
    ensure_customers_tables()

    clean_customer_code = customer_code.strip()
    clean_invoice_number = invoice_number.strip()

    if not clean_customer_code:
        raise HTTPException(
            status_code=400,
            detail="El código del cliente es obligatorio.",
        )

    if not clean_invoice_number:
        raise HTTPException(
            status_code=400,
            detail="El número de factura es obligatorio.",
        )

    if amount <= 0:
        raise HTTPException(
            status_code=400,
            detail="El monto de compra debe ser mayor a cero.",
        )

    points_earned = calculate_points(amount)
    created_at = datetime.now().isoformat()

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *
        FROM customers
        WHERE code = %s
        """,
        (clean_customer_code,),
    )

    customer = cursor.fetchone()

    if not customer:
        cursor.close()
        conn.close()
        raise HTTPException(
            status_code=404,
            detail="No encontramos un cliente asociado a ese código QR.",
        )

    cursor.execute(
        """
        INSERT INTO purchases (
            customer_code,
            invoice_number,
            amount,
            points_earned,
            created_at
        )
        VALUES (%s, %s, %s, %s, %s)
        """,
        (
            clean_customer_code,
            clean_invoice_number,
            amount,
            points_earned,
            created_at,
        ),
    )

    cursor.execute(
        """
        UPDATE customers
        SET points = points + %s
        WHERE code = %s
        RETURNING points
        """,
        (
            points_earned,
            clean_customer_code,
        ),
    )

    updated_customer = cursor.fetchone()

    conn.commit()
    cursor.close()
    conn.close()

    return {
        "success": True,
        "message": "Compra registrada correctamente.",
        "customer_code": clean_customer_code,
        "invoice_number": clean_invoice_number,
        "amount": amount,
        "points_earned": points_earned,
        "total_points": updated_customer["points"],
    }


@router.get("/admin/list")
def list_customers(
    request: Request,
    x_admin_token: str | None = Header(default=None),
):
    check_rate_limit(
        request=request,
        key="customers_admin_list",
        max_requests=60,
        window_seconds=60,
    )

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
def register_customer(
    payload: CustomerRegisterRequest,
    request: Request,
):
    check_rate_limit(
        request=request,
        key="customer_register",
        max_requests=5,
        window_seconds=600,
    )

    clean_name = payload.name.strip()
    clean_email = payload.email.strip().lower()
    clean_whatsapp = payload.whatsapp.strip()

    if len(clean_name) < 3:
        raise HTTPException(
            status_code=400,
            detail="El nombre debe tener al menos 3 caracteres.",
        )

    if len(clean_whatsapp) < 8:
        raise HTTPException(
            status_code=400,
            detail="El número de WhatsApp no parece válido.",
        )

    ensure_customers_tables()

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *
        FROM customers
        WHERE email = %s
        """,
        (clean_email,),
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
            clean_name,
            clean_email,
            clean_whatsapp,
            0,
            created_at,
        ),
    )

    conn.commit()
    cursor.close()
    conn.close()

    email_sent = send_customer_welcome_email(
        customer_name=clean_name,
        customer_email=clean_email,
        customer_code=customer_code,
    )

    internal_email_sent = send_internal_new_customer_email(
        customer_name=clean_name,
        customer_email=clean_email,
        customer_whatsapp=clean_whatsapp,
        customer_code=customer_code,
    )

    customer_whatsapp_url = build_customer_welcome_whatsapp_url(
        customer_name=clean_name,
        customer_whatsapp=clean_whatsapp,
        customer_code=customer_code,
    )

    shirleys_whatsapp_url = build_internal_new_customer_whatsapp_url(
        customer_name=clean_name,
        customer_email=clean_email,
        customer_whatsapp=clean_whatsapp,
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


@router.post("/purchase")
def register_purchase_by_body(
    payload: PurchaseRegisterByBodyRequest,
    request: Request,
    x_admin_token: str | None = Header(default=None),
):
    check_rate_limit(
        request=request,
        key="customer_purchase",
        max_requests=40,
        window_seconds=60,
    )

    verify_admin_token(x_admin_token)

    return create_purchase_for_customer(
        customer_code=payload.customer_code,
        invoice_number=payload.invoice_number,
        amount=payload.amount,
    )


@router.post("/{customer_code}/purchases")
def register_purchase(
    customer_code: str,
    payload: PurchaseRegisterRequest,
    request: Request,
    x_admin_token: str | None = Header(default=None),
):
    check_rate_limit(
        request=request,
        key="customer_purchase_by_code",
        max_requests=40,
        window_seconds=60,
    )

    verify_admin_token(x_admin_token)

    return create_purchase_for_customer(
        customer_code=customer_code,
        invoice_number=payload.invoice_number,
        amount=payload.amount,
    )


@router.get("/email/{customer_email}")
def get_customer_by_email(
    customer_email: str,
    request: Request,
):
    check_rate_limit(
        request=request,
        key="customer_lookup_by_email",
        max_requests=80,
        window_seconds=60,
    )

    clean_email = customer_email.strip().lower()

    if not clean_email:
        raise HTTPException(
            status_code=400,
            detail="El correo electrónico del cliente es obligatorio.",
        )

    ensure_customers_tables()

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *
        FROM customers
        WHERE LOWER(email) = %s
        """,
        (clean_email,),
    )

    customer = cursor.fetchone()

    cursor.close()
    conn.close()

    if not customer:
        raise HTTPException(
            status_code=404,
            detail="No encontramos un cliente asociado a ese correo electrónico.",
        )

    return build_customer_response(customer)


@router.get("/{customer_code}")
def get_customer(
    customer_code: str,
    request: Request,
):
    check_rate_limit(
        request=request,
        key="customer_lookup",
        max_requests=80,
        window_seconds=60,
    )

    clean_customer_code = customer_code.strip()

    if not clean_customer_code:
        raise HTTPException(
            status_code=400,
            detail="El código del cliente es obligatorio.",
        )

    ensure_customers_tables()

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *
        FROM customers
        WHERE code = %s
        """,
        (clean_customer_code,),
    )

    customer = cursor.fetchone()

    cursor.close()
    conn.close()

    if not customer:
        raise HTTPException(
            status_code=404,
            detail="No encontramos un cliente asociado a ese código QR.",
        )

    return build_customer_response(customer)