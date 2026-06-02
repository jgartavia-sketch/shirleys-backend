import os
import re
import smtplib
from io import BytesIO
from email.message import EmailMessage
from urllib.parse import quote

import qrcode
from dotenv import load_dotenv

load_dotenv()

EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:4200").rstrip("/")

SHIRLEYS_WHATSAPP_NUMBER = os.getenv("SHIRLEYS_WHATSAPP_NUMBER", "50688335888")

INTERNAL_NEW_CUSTOMER_EMAIL_TO = os.getenv(
    "INTERNAL_NEW_CUSTOMER_EMAIL_TO",
    "atencionalcliente@shirleyscr.com",
)

INTERNAL_NEW_CUSTOMER_EMAIL_CC = os.getenv(
    "INTERNAL_NEW_CUSTOMER_EMAIL_CC",
    "shirleyag@hotmail.es",
)


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


def normalize_whatsapp_number(phone: str | None) -> str:
    if not phone:
        return ""

    cleaned = re.sub(r"\D", "", phone)

    if not cleaned:
        return ""

    if cleaned.startswith("506"):
        return cleaned

    return f"506{cleaned}"


def build_customer_welcome_whatsapp_url(
    customer_name: str,
    customer_whatsapp: str,
    customer_code: str,
) -> str:
    normalized_phone = normalize_whatsapp_number(customer_whatsapp)
    customer_card_url = f"{FRONTEND_URL}/customers/{customer_code}"

    message = f"""Hola, {customer_name}. Bienvenido a Shirley’s.

Tu registro fue exitoso.

Ahora tienes tu tarjeta digital de cliente frecuente, donde podrás acumular puntos en cada compra y canjearlos por promociones, beneficios y premios exclusivos.

Código de cliente:
{customer_code}

Tu tarjeta digital:
{customer_card_url}

También te hemos enviado a tu correo electrónico la imagen de tu código QR personal. Te recomendamos descargarla y guardarla en tus imágenes favoritas para tenerla siempre disponible cuando visites Shirley’s o realices un pedido.

Guarda tu tarjeta digital y presenta tu QR cada vez que visites Shirley’s para acumular puntos.

Menú y pedidos:
https://shirleyscr.com/menu

Cotizaciones para eventos y Catering Service:
https://shirleyscr.com/catering

Gracias por formar parte de Shirley’s.

Tu próxima visita podría acercarte a tu próxima recompensa."""

    return f"https://wa.me/{normalized_phone}?text={quote(message, safe='')}"


def build_internal_new_customer_whatsapp_url(
    customer_name: str,
    customer_email: str,
    customer_whatsapp: str,
    customer_code: str,
) -> str:
    normalized_shirleys_phone = normalize_whatsapp_number(SHIRLEYS_WHATSAPP_NUMBER)
    customer_card_url = f"{FRONTEND_URL}/customers/{customer_code}"

    message = f"""Nuevo registro en Shirley’s Customers.

Nombre:
{customer_name}

Correo:
{customer_email}

WhatsApp:
{customer_whatsapp}

Código de cliente:
{customer_code}

Tarjeta digital:
{customer_card_url}"""

    return f"https://wa.me/{normalized_shirleys_phone}?text={quote(message, safe='')}"


def send_email_message(message: EmailMessage) -> bool:
    if not EMAIL_ADDRESS or not EMAIL_PASSWORD:
        print("Faltan EMAIL_ADDRESS o EMAIL_PASSWORD en el archivo .env.")
        return False

    try:
        with smtplib.SMTP_SSL("smtp.hostinger.com", 465) as smtp:
            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            smtp.send_message(message)

        return True

    except Exception as error:
        print("ERROR SMTP:", error)
        return False


def send_customer_welcome_email(
    customer_name: str,
    customer_email: str,
    customer_code: str,
) -> bool:
    customer_card_url = f"{FRONTEND_URL}/customers/{customer_code}"
    qr_image = generate_customer_qr(customer_code)

    message = EmailMessage()
    message["Subject"] = "Tu QR de Shirley’s Customers"
    message["From"] = EMAIL_ADDRESS or ""
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

    was_sent = send_email_message(message)

    if was_sent:
        print("Correo con QR enviado correctamente.")
    else:
        print("No se pudo enviar el correo con QR al cliente.")

    return was_sent


def send_internal_new_customer_email(
    customer_name: str,
    customer_email: str,
    customer_whatsapp: str,
    customer_code: str,
) -> bool:
    customer_card_url = f"{FRONTEND_URL}/customers/{customer_code}"
    whatsapp_notification_url = build_internal_new_customer_whatsapp_url(
        customer_name=customer_name,
        customer_email=customer_email,
        customer_whatsapp=customer_whatsapp,
        customer_code=customer_code,
    )

    message = EmailMessage()
    message["Subject"] = "Nuevo cliente registrado en Shirley’s Customers"
    message["From"] = EMAIL_ADDRESS or ""
    message["To"] = INTERNAL_NEW_CUSTOMER_EMAIL_TO

    if INTERNAL_NEW_CUSTOMER_EMAIL_CC:
        message["Cc"] = INTERNAL_NEW_CUSTOMER_EMAIL_CC

    text_content = f"""
Nuevo cliente registrado en Shirley’s Customers.

Nombre:
{customer_name}

Correo:
{customer_email}

WhatsApp:
{customer_whatsapp}

Código de cliente:
{customer_code}

Tarjeta digital:
{customer_card_url}

Notificación por WhatsApp:
{whatsapp_notification_url}
"""

    html_content = f"""
    <html>
      <body style="margin:0; padding:0; background:#0b0f0c; font-family:Arial, sans-serif; color:#f8f1df;">
        <div style="max-width:640px; margin:0 auto; padding:32px;">
          <div style="background:linear-gradient(135deg,#111a14,#1d2b20); border:1px solid rgba(212,175,55,.35); border-radius:24px; padding:32px;">

            <h1 style="margin:0 0 12px; color:#d4af37; font-size:26px;">
              Nuevo cliente registrado
            </h1>

            <p style="font-size:15px; line-height:1.7; color:#e8dec5;">
              Se registró un nuevo cliente en <strong>Shirley’s Customers</strong>.
            </p>

            <div style="background:rgba(255,255,255,.08); border-radius:18px; padding:20px; margin:24px 0;">
              <p style="margin:0 0 10px;"><strong style="color:#d4af37;">Nombre:</strong> {customer_name}</p>
              <p style="margin:0 0 10px;"><strong style="color:#d4af37;">Correo:</strong> {customer_email}</p>
              <p style="margin:0 0 10px;"><strong style="color:#d4af37;">WhatsApp:</strong> {customer_whatsapp}</p>
              <p style="margin:0;"><strong style="color:#d4af37;">Código:</strong> {customer_code}</p>
            </div>

            <a href="{customer_card_url}" style="display:inline-block; margin-right:10px; margin-top:10px; background:#d4af37; color:#111; text-decoration:none; padding:13px 20px; border-radius:999px; font-weight:bold;">
              Ver tarjeta digital
            </a>

            <a href="{whatsapp_notification_url}" style="display:inline-block; margin-top:10px; background:#f8f1df; color:#111; text-decoration:none; padding:13px 20px; border-radius:999px; font-weight:bold;">
              Abrir WhatsApp
            </a>

            <p style="margin-top:28px; font-size:13px; color:#cfc7ad;">
              Registro generado automáticamente por el sistema de Shirley’s.
            </p>
          </div>
        </div>
      </body>
    </html>
    """

    message.set_content(text_content)
    message.add_alternative(html_content, subtype="html")

    was_sent = send_email_message(message)

    if was_sent:
        print("Correo interno de nuevo cliente enviado correctamente.")
    else:
        print("No se pudo enviar el correo interno de nuevo cliente.")

    return was_sent