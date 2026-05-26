import os
import shutil
import sqlite3
from datetime import datetime, timedelta

import jwt
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

load_dotenv()

router = APIRouter()

DB_PATH = "shirleys_customers.db"
QR_FOLDER = "static/customer_qr"

STAFF_PASSWORD = os.getenv("STAFF_PASSWORD")
STAFF_JWT_SECRET = os.getenv("STAFF_JWT_SECRET", "shirleys-staff-secret-dev")
ADMIN_CUSTOMERS_TOKEN = os.getenv("ADMIN_CUSTOMERS_TOKEN")


class StaffLoginRequest(BaseModel):
    password: str


class StaffClearRequest(BaseModel):
    password: str
    confirm: str


def create_staff_token():
    expiration = datetime.utcnow() + timedelta(hours=8)

    payload = {
        "role": "staff",
        "exp": expiration,
    }

    return jwt.encode(payload, STAFF_JWT_SECRET, algorithm="HS256")


@router.post("/login")
def staff_login(data: StaffLoginRequest):
    if not STAFF_PASSWORD:
        raise HTTPException(
            status_code=500,
            detail="STAFF_PASSWORD no está configurado en el servidor.",
        )

    if data.password != STAFF_PASSWORD:
        raise HTTPException(
            status_code=401,
            detail="Contraseña staff incorrecta.",
        )

    if not ADMIN_CUSTOMERS_TOKEN:
        raise HTTPException(
            status_code=500,
            detail="ADMIN_CUSTOMERS_TOKEN no está configurado en el servidor.",
        )

    return {
        "success": True,
        "message": "Acceso staff autorizado.",
        "token": ADMIN_CUSTOMERS_TOKEN,
        "token_type": "admin-customers-token",
        "expires_in_hours": 8,
    }


@router.post("/clear-test-data")
def clear_test_data(data: StaffClearRequest):
    if not STAFF_PASSWORD:
        raise HTTPException(
            status_code=500,
            detail="STAFF_PASSWORD no está configurado en el servidor.",
        )

    if data.password != STAFF_PASSWORD:
        raise HTTPException(
            status_code=401,
            detail="Contraseña staff incorrecta.",
        )

    if data.confirm != "CLEAR_SHIRLEYS_CUSTOMERS":
        raise HTTPException(
            status_code=400,
            detail="Confirmación inválida.",
        )

    deleted_customers = 0
    deleted_purchases = 0
    deleted_history = 0

    if os.path.exists(DB_PATH):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        try:
            deleted_history = cursor.execute("SELECT COUNT(*) FROM points_history").fetchone()[0]
            deleted_purchases = cursor.execute("SELECT COUNT(*) FROM purchases").fetchone()[0]
            deleted_customers = cursor.execute("SELECT COUNT(*) FROM customers").fetchone()[0]

            cursor.execute("DELETE FROM points_history")
            cursor.execute("DELETE FROM purchases")
            cursor.execute("DELETE FROM customers")

            conn.commit()
        finally:
            conn.close()

    if os.path.exists(QR_FOLDER):
        shutil.rmtree(QR_FOLDER)

    os.makedirs(QR_FOLDER, exist_ok=True)

    return {
        "success": True,
        "message": "Datos de prueba eliminados correctamente.",
        "deleted": {
            "customers": deleted_customers,
            "purchases": deleted_purchases,
            "points_history": deleted_history,
        },
        "qr_folder_reset": True,
    }