import os
import smtplib
from io import BytesIO
from email.message import EmailMessage
from dotenv import load_dotenv
import qrcode

load_dotenv()

EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

FRONTEND_URL = os.getenv("FRONTEND_URL", "https://shirleys-front.vercel.app")


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


def send_customer_welcome_email(customer_name: str, customer_email: str, customer_code: str) -> bool:

    print("EMAIL_ADDRESS:", EMAIL_ADDRESS)
    print("EMAIL_PASSWORD EXISTS:", bool(EMAIL_PASSWORD))

    if not EMAIL_ADDRESS or not EMAIL_PASSWORD:
        print("Faltan EMAIL_ADDRESS o EMAIL_PASSWORD en Render.")
        return False

    customer_card_url = f"{FRONTEND_URL}/customers/{customer_code}"
    qr_image = generate_customer_qr(customer_code)

    message = EmailMessage()
    message["Subject"] = "Tu QR de Shirley’s Customers"
    message["From"] = EMAIL_ADDRESS
    message["To"] = customer_email

    message.set_content(
        f"""
Hola {customer_name},

¡Bienvenido a Shirley’s Customers!

Tu registro fue exitoso.

Adjunto encontrarás tu código QR personal.

Al escanearlo, se abrirá tu tarjeta digital de cliente:

{customer_card_url}

Ahí podrás ver tu perfil, código de cliente y puntos acumulados.

Gracias por formar parte de Shirley’s.
"""
    )

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