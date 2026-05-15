from datetime import datetime
import sqlite3
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr, Field

router = APIRouter()

DB_PATH = Path("shirleys_customers.db")


class CateringQuoteRequest(BaseModel):
    event_type: str = Field(..., min_length=2)
    name: str = Field(..., min_length=2)
    email: EmailStr
    whatsapp: str = Field(..., min_length=6)
    event_date: str = Field(..., min_length=8)
    message: str | None = ""


def get_connection():
    return sqlite3.connect(DB_PATH)


def init_catering_table():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS catering_quotes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            whatsapp TEXT NOT NULL,
            event_date TEXT NOT NULL,
            message TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL
        )
        """
    )

    conn.commit()
    conn.close()


init_catering_table()


@router.post("/quote")
def create_catering_quote(request: CateringQuoteRequest):
    try:
        created_at = datetime.now().isoformat(timespec="seconds")

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO catering_quotes (
                event_type,
                name,
                email,
                whatsapp,
                event_date,
                message,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request.event_type,
                request.name,
                request.email,
                request.whatsapp,
                request.event_date,
                request.message or "",
                created_at,
            ),
        )

        conn.commit()
        quote_id = cursor.lastrowid
        conn.close()

        return {
            "success": True,
            "message": "Solicitud de catering registrada correctamente.",
            "quote": {
                "id": quote_id,
                "event_type": request.event_type,
                "name": request.name,
                "email": request.email,
                "whatsapp": request.whatsapp,
                "event_date": request.event_date,
                "message": request.message or "",
                "status": "pending",
                "created_at": created_at,
            },
        }

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"No se pudo registrar la solicitud de catering: {str(error)}",
        )