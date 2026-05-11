from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from datetime import datetime
import sqlite3
import os
import qrcode

from app.email_service import send_customer_welcome_email

router = APIRouter()

DB_PATH = "shirleys_customers.db"
QR_FOLDER = "static/customer_qr"


class CustomerRegister(BaseModel):
    name: str
    email: EmailStr
    whatsapp: str


class PurchaseRegister(BaseModel):
    customer_code: str
    invoice_number: str
    amount: float


def get_connection():
    return sqlite3.connect(DB_PATH)


def calculate_points(amount: float):
    if amount >= 15000:
        return 9
    if amount >= 10000:
        return 7
    if amount >= 5000:
        return 3
    return 0


def generate_customer_qr(customer_code: str):
    os.makedirs(QR_FOLDER, exist_ok=True)

    customer_profile_url = f"http://localhost:4200/customers/{customer_code}"
    qr_filename = f"{customer_code}.png"
    qr_path = os.path.join(QR_FOLDER, qr_filename)

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )

    qr.add_data(customer_profile_url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    img.save(qr_path)

    return {
        "qr_path": qr_path,
        "qr_url": f"/static/customer_qr/{qr_filename}",
        "profile_url": customer_profile_url,
    }


def init_database():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            whatsapp TEXT UNIQUE NOT NULL,
            points INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_code TEXT NOT NULL,
            invoice_number TEXT UNIQUE NOT NULL,
            amount REAL NOT NULL,
            points_earned INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (customer_code) REFERENCES customers(code)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS points_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_code TEXT NOT NULL,
            points INTEGER NOT NULL,
            reason TEXT NOT NULL,
            invoice_number TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (customer_code) REFERENCES customers(code)
        )
    """)

    conn.commit()
    conn.close()


init_database()


@router.post("/register")
def register_customer(customer: CustomerRegister):
    clean_name = customer.name.strip()
    clean_email = customer.email.strip().lower()
    clean_whatsapp = customer.whatsapp.strip()

    if not clean_name:
        raise HTTPException(status_code=400, detail="El nombre es obligatorio.")

    if not clean_whatsapp:
        raise HTTPException(status_code=400, detail="El WhatsApp es obligatorio.")

    customer_code = f"SHR-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    created_at = datetime.now().isoformat()

    conn = get_connection()
    cursor = conn.cursor()

    existing_customer = cursor.execute(
        """
        SELECT id FROM customers
        WHERE email = ? OR whatsapp = ?
        """,
        (clean_email, clean_whatsapp),
    ).fetchone()

    if existing_customer:
        conn.close()
        raise HTTPException(
            status_code=409,
            detail="Ya existe un cliente registrado con ese correo o WhatsApp.",
        )

    cursor.execute(
        """
        INSERT INTO customers (code, name, email, whatsapp, points, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
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
    conn.close()

    qr_data = generate_customer_qr(customer_code)

    email_sent = send_customer_welcome_email(
        customer_name=clean_name,
        customer_email=clean_email,
        customer_code=customer_code,
    )

    return {
        "success": True,
        "message": "Cliente registrado exitosamente",
        "customer": {
            "code": customer_code,
            "name": clean_name,
            "email": clean_email,
            "whatsapp": clean_whatsapp,
            "points": 0,
            "created_at": created_at,
            "profile_url": qr_data["profile_url"],
            "qr_url": qr_data["qr_url"],
            "qr_path": qr_data["qr_path"],
        },
        "email_sent": email_sent,
    }


@router.get("/")
def get_customers():
    conn = get_connection()
    cursor = conn.cursor()

    rows = cursor.execute(
        """
        SELECT code, name, email, whatsapp, points, created_at
        FROM customers
        ORDER BY id DESC
        """
    ).fetchall()

    conn.close()

    customers = [
        {
            "code": row[0],
            "name": row[1],
            "email": row[2],
            "whatsapp": row[3],
            "points": row[4],
            "created_at": row[5],
            "profile_url": f"http://localhost:4200/customers/{row[0]}",
            "qr_url": f"/static/customer_qr/{row[0]}.png",
        }
        for row in rows
    ]

    return {
        "total_customers": len(customers),
        "customers": customers,
    }


@router.get("/{customer_code}")
def get_customer_by_code(customer_code: str):
    conn = get_connection()
    cursor = conn.cursor()

    customer = cursor.execute(
        """
        SELECT code, name, email, whatsapp, points, created_at
        FROM customers
        WHERE code = ?
        """,
        (customer_code,),
    ).fetchone()

    if not customer:
        conn.close()
        raise HTTPException(status_code=404, detail="Cliente no encontrado.")

    purchases = cursor.execute(
        """
        SELECT invoice_number, amount, points_earned, created_at
        FROM purchases
        WHERE customer_code = ?
        ORDER BY id DESC
        """,
        (customer_code,),
    ).fetchall()

    history = cursor.execute(
        """
        SELECT points, reason, invoice_number, created_at
        FROM points_history
        WHERE customer_code = ?
        ORDER BY id DESC
        """,
        (customer_code,),
    ).fetchall()

    conn.close()

    return {
        "customer": {
            "code": customer[0],
            "name": customer[1],
            "email": customer[2],
            "whatsapp": customer[3],
            "points": customer[4],
            "created_at": customer[5],
            "profile_url": f"http://localhost:4200/customers/{customer[0]}",
            "qr_url": f"/static/customer_qr/{customer[0]}.png",
        },
        "purchases": [
            {
                "invoice_number": row[0],
                "amount": row[1],
                "points_earned": row[2],
                "created_at": row[3],
            }
            for row in purchases
        ],
        "points_history": [
            {
                "points": row[0],
                "reason": row[1],
                "invoice_number": row[2],
                "created_at": row[3],
            }
            for row in history
        ],
    }


@router.post("/purchase")
def register_purchase(purchase: PurchaseRegister):
    clean_customer_code = purchase.customer_code.strip()
    clean_invoice_number = purchase.invoice_number.strip()
    amount = purchase.amount

    if not clean_customer_code:
        raise HTTPException(status_code=400, detail="El código del cliente es obligatorio.")

    if not clean_invoice_number:
        raise HTTPException(status_code=400, detail="El número de factura es obligatorio.")

    if amount <= 0:
        raise HTTPException(status_code=400, detail="El monto debe ser mayor a cero.")

    points_earned = calculate_points(amount)
    created_at = datetime.now().isoformat()

    conn = get_connection()
    cursor = conn.cursor()

    customer = cursor.execute(
        """
        SELECT code, name, points
        FROM customers
        WHERE code = ?
        """,
        (clean_customer_code,),
    ).fetchone()

    if not customer:
        conn.close()
        raise HTTPException(status_code=404, detail="Cliente no encontrado.")

    existing_invoice = cursor.execute(
        """
        SELECT id FROM purchases
        WHERE invoice_number = ?
        """,
        (clean_invoice_number,),
    ).fetchone()

    if existing_invoice:
        conn.close()
        raise HTTPException(status_code=409, detail="Ese número de factura ya fue registrado.")

    cursor.execute(
        """
        INSERT INTO purchases (customer_code, invoice_number, amount, points_earned, created_at)
        VALUES (?, ?, ?, ?, ?)
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
        INSERT INTO points_history (customer_code, points, reason, invoice_number, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            clean_customer_code,
            points_earned,
            "Compra registrada",
            clean_invoice_number,
            created_at,
        ),
    )

    cursor.execute(
        """
        UPDATE customers
        SET points = points + ?
        WHERE code = ?
        """,
        (points_earned, clean_customer_code),
    )

    updated_customer = cursor.execute(
        """
        SELECT code, name, email, whatsapp, points, created_at
        FROM customers
        WHERE code = ?
        """,
        (clean_customer_code,),
    ).fetchone()

    conn.commit()
    conn.close()

    return {
        "success": True,
        "message": "Compra registrada y puntos actualizados.",
        "purchase": {
            "customer_code": clean_customer_code,
            "invoice_number": clean_invoice_number,
            "amount": amount,
            "points_earned": points_earned,
            "created_at": created_at,
        },
        "customer": {
            "code": updated_customer[0],
            "name": updated_customer[1],
            "email": updated_customer[2],
            "whatsapp": updated_customer[3],
            "points": updated_customer[4],
            "created_at": updated_customer[5],
            "profile_url": f"http://localhost:4200/customers/{updated_customer[0]}",
            "qr_url": f"/static/customer_qr/{updated_customer[0]}.png",
        },
    }