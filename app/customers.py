from fastapi import APIRouter
from pydantic import BaseModel
from datetime import datetime

from app.email_service import send_customer_welcome_email

router = APIRouter()

customers_db = []


class CustomerRegister(BaseModel):
    name: str
    email: str
    whatsapp: str


@router.post("/register")
def register_customer(customer: CustomerRegister):

    customer_code = f"SHR-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    email_sent = send_customer_welcome_email(
        customer_name=customer.name,
        customer_email=customer.email,
        customer_code=customer_code,
    )

    new_customer = {
        "code": customer_code,
        "name": customer.name,
        "email": customer.email,
        "whatsapp": customer.whatsapp,
        "points": 0,
    }

    customers_db.append(new_customer)

    return {
        "success": True,
        "message": "Cliente registrado exitosamente",
        "customer": new_customer,
        "email_sent": email_sent,
    }


@router.get("/")
def get_customers():
    return {
        "total_customers": len(customers_db),
        "customers": customers_db,
    }