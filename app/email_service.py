import os
import smtplib
from io import BytesIO
from email.message import EmailMessage

import qrcode
from dotenv import load_dotenv

load_dotenv()

EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:4200")


def generate_customer_qr(customer_code: str) -> bytes:
    customer_card_url = f"{FRONTEND_URL}/customers/{customer_code}"

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )

    qr.add_data(customer_card_url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    return buffer.read()


def send_customer_welcome_email(
    customer_name: str,
    customer_email: str,
    customer_code: str,
) -> bool:
    if not EMAIL_ADDRESS or not EMAIL_PASSWORD:
        print("Faltan EMAIL_ADDRESS o EMAIL_PASSWORD en el archivo .env.")
        return False

    customer_card_url = f"{FRONTEND_URL}/customers/{customer_code}"
    qr_image = generate_customer_qr(customer_code)

    message = EmailMessage()
    message["Subject"] = "Tu QR de Shirley’s Customers"
    message["From"] = EMAIL_ADDRESS
    message["To"] = customer_email

    text_content = f"""
Hola {customer_name},

¡Bienvenido a Shirley’s Customers!

Tu registro fue exitoso.

Código de cliente:
{customer_code}

Adjunto encontrarás tu código QR personal.

También puedes abrir tu tarjeta digital aquí:
{customer_card_url}

Gracias por formar parte de Shirley’s.
"""

    html_content = f"""
    <html>
      <body style="margin:0; padding:0; background:#0b0f0c; font-family:Arial, sans-serif; color:#f8f1df;">
        <div style="max-width:620px; margin:0 auto; padding:32px;">
          <div style="background:linear-gradient(135deg,#111a14,#1d2b20); border:1px solid rgba(212,175,55,.35); border-radius:24px; padding:32px;">
            
            <h1 style="margin:0 0 12px; color:#d4af37; font-size:28px;">
              Shirley’s Customers
            </h1>

            <p style="font-size:16px; line-height:1.6;">
              Hola <strong>{customer_name}</strong>,
            </p>

            <p style="font-size:16px; line-height:1.6;">
              Tu registro fue exitoso. Ya tienes tu tarjeta digital de fidelización.
            </p>

            <div style="background:rgba(255,255,255,.08); border-radius:18px; padding:20px; margin:24px 0;">
              <p style="margin:0 0 8px; color:#d4af37;">Código de cliente</p>
              <h2 style="margin:0; color:#ffffff; letter-spacing:1px;">{customer_code}</h2>
            </div>

            <p style="font-size:16px; line-height:1.6;">
              Adjuntamos tu QR personal. Guárdalo y preséntalo en el restaurante para acumular puntos.
            </p>

            <a href="{customer_card_url}" style="display:inline-block; margin-top:18px; background:#d4af37; color:#111; text-decoration:none; padding:14px 22px; border-radius:999px; font-weight:bold;">
              Ver mi tarjeta digital
            </a>

            <p style="margin-top:28px; font-size:13px; color:#cfc7ad;">
              Gracias por formar parte de Shirley’s. Esto apenas empieza.
            </p>
          </div>
        </div>
      </body>
    </html>
    """

    message.set_content(text_content)
    message.add_alternative(html_content, subtype="html")

    message.add_attachment(
        qr_image,
        maintype="image",
        subtype="png",
        filename=f"shirleys-customer-{customer_code}.png",
    )

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            smtp.send_message(message)

        print("Correo con QR enviado correctamente.")
        return True

    except Exception as error:
        print("ERROR SMTP:", error)
        return False