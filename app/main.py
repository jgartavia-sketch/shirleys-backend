import os
from typing import Iterable

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from app.customers import router as customers_router
from app.staff_auth import router as staff_router
from app.catering import router as catering_router
from app.admin import router as admin_router
from app.orders import router as orders_router


def parse_csv_env(value: str | None) -> list[str]:
    if not value:
        return []

    return [
        item.strip()
        for item in value.split(",")
        if item.strip()
    ]


DEFAULT_ALLOWED_ORIGINS = [
    "http://localhost:4200",
    "http://localhost:5173",
    "https://shirleys-front.vercel.app",
    "https://shirleys-frontend.vercel.app",
    "https://shirleyscr.com",
    "https://www.shirleyscr.com",
]

DEFAULT_ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
    "*.onrender.com",
    "shirleyscr.com",
    "www.shirleyscr.com",
]

ALLOWED_ORIGINS = parse_csv_env(os.getenv("ALLOWED_ORIGINS")) or DEFAULT_ALLOWED_ORIGINS
ALLOWED_HOSTS = parse_csv_env(os.getenv("ALLOWED_HOSTS")) or DEFAULT_ALLOWED_HOSTS


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(self), microphone=(), geolocation=()"

        return response


app = FastAPI(
    title="Shirley's Backend",
    description="Backend para Shirley's Customers, Catering Service, Pedidos WhatsApp y Panel Admin",
    version="1.0.0",
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=ALLOWED_HOSTS,
)

app.add_middleware(SecurityHeadersMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "Accept",
        "Origin",
        "X-Requested-With",
        "X-Admin-Token",
    ],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(
    customers_router,
    prefix="/api/customers",
    tags=["Customers"],
)

app.include_router(
    staff_router,
    prefix="/api/staff",
    tags=["Staff"],
)

app.include_router(
    catering_router,
    prefix="/api/catering",
    tags=["Catering"],
)

app.include_router(
    admin_router,
    prefix="/api/admin",
    tags=["Admin"],
)

app.include_router(
    orders_router,
    prefix="/api/orders",
    tags=["WhatsApp Orders"],
)


@app.get("/")
def home():
    return {
        "message": "Shirley's Backend is running",
        "status": "ok",
    }


@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "service": "shirleys-backend",
        "allowed_origins": ALLOWED_ORIGINS,
    }