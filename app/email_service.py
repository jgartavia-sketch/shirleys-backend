import os
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv

load_dotenv()

EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")


def send_customer_welcome_email(customer_name: str, customer_email: str, customer_code: str) -> bool:

    print("EMAIL_ADDRESS:", EMAIL_ADDRESS)
    print("EMAIL_PASSWORD EXISTS:", bool(EMAIL_PASSWORD))

    if not EMAIL_ADDRESS or not EMAIL_PASSWORD:
        print("Faltan EMAIL_ADDRESS o EMAIL_PASSWORD en Render.")
        return False

    message = EmailMessage()
    message["Subject"] = "Bienvenido a Shirley’s Customers"
    message["From"] = EMAIL_ADDRESS
    message["To"] = customer_email

    message.set_content(
        f"""
Hola {customer_name},

¡Bienvenido a Shirley’s Customers!

Tu registro fue exitoso.

Tu código de cliente es: {customer_code}

Muy pronto podrás utilizar tu código QR para acumular puntos y beneficios especiales.

Gracias por formar parte de Shirley’s.
"""
    )

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            smtp.send_message(message)

        print("Correo enviado correctamente.")
        return True

    except Exception as error:
        print("ERROR SMTP:", error)
        return False