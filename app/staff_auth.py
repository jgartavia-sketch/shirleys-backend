import os
from datetime import datetime, timedelta

import jwt
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

load_dotenv()

router = APIRouter()

STAFF_PASSWORD = os.getenv("STAFF_PASSWORD")
STAFF_JWT_SECRET = os.getenv("STAFF_JWT_SECRET", "shirleys-staff-secret-dev")


class StaffLoginRequest(BaseModel):
    password: str


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

    token = create_staff_token()

    return {
        "success": True,
        "message": "Acceso staff autorizado.",
        "token": token,
        "token_type": "bearer",
        "expires_in_hours": 8,
    }