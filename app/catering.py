from datetime import datetime
import os
import smtplib
import sqlite3
from pathlib import Path
from email.message import EmailMessage

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr, Field

load_dotenv()

router = APIRouter()

DB_PATH = Path("shirleys_customers.db")

EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
BUSINESS_EMAIL = "shirleyag@hotmail.es"


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


def send_catering_quote_email(request: CateringQuoteRequest, quote_id: int, created_at: str) -> bool:
    if not EMAIL_ADDRESS or not EMAIL_PASSWORD:
        print("Faltan EMAIL_ADDRESS o EMAIL_PASSWORD en el archivo .env.")
        return False

    subject = f"Nueva cotización de catering #{quote_id} - Shirley’s"

    text_content = f"""
Nueva solicitud de cotización de catering

ID de solicitud: {quote_id}
Fecha de registro: {created_at}

Tipo de evento:
{request.event_type}

Nombre:
{request.name}

Correo:
{request.email}

WhatsApp:
{request.whatsapp}

Fecha del evento:
{request.event_date}

Mensaje:
{request.message or "Sin mensaje adicional."}
"""

    html_content = f"""
    <html>
      <body style="margin:0; padding:0; background:#0b0f0c; font-family:Arial, sans-serif; color:#f8f1df;">
        <div style="max-width:680px; margin:0 auto; padding:32px;">
          <div style="background:linear-gradient(135deg,#111a14,#1d2b20); border:1px solid rgba(212,175,55,.35); border-radius:24px; padding:32px;">
            
            <h1 style="margin:0 0 12px; color:#d4af37; font-size:28px;">
              Nueva cotización de catering
            </h1>

            <p style="font-size:15px; color:#cfc7ad;">
              Solicitud registrada desde la página web de Shirley’s.
            </p>

            <div style="background:rgba(255,255,255,.08); border-radius:18px; padding:20px; margin:24px 0;">
              <p><strong>ID:</strong> #{quote_id}</p>
              <p><strong>Fecha de registro:</strong> {created_at}</p>
              <p><strong>Tipo de evento:</strong> {request.event_type}</p>
              <p><strong>Nombre:</strong> {request.name}</p>
              <p><strong>Correo:</strong> {request.email}</p>
              <p><strong>WhatsApp:</strong> {request.whatsapp}</p>
              <p><strong>Fecha del evento:</strong> {request.event_date}</p>
            </div>

            <div style="background:rgba(212,175,55,.10); border-radius:18px; padding:20px;">
              <p style="margin:0 0 8px; color:#d4af37;"><strong>Mensaje del cliente</strong></p>
              <p style="margin:0; line-height:1.6;">{request.message or "Sin mensaje adicional."}</p>
            </div>

          </div>
        </div>
      </body>
    </html>
    """

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = EMAIL_ADDRESS
    message["To"] = BUSINESS_EMAIL
    message["Cc"] = request.email

    message.set_content(text_content)
    message.add_alternative(html_content, subtype="html")

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            smtp.send_message(message)

        print("Correo de cotización enviado correctamente.")
        return True

    except Exception as error:
        print("ERROR SMTP CATERING:", error)
        return False


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

        email_sent = send_catering_quote_email(request, quote_id, created_at)

        return {
            "success": True,
            "message": "Solicitud de catering registrada correctamente.",
            "email_sent": email_sent,
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