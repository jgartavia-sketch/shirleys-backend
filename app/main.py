from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.customers import router as customers_router

app = FastAPI(
    title="Shirley's Backend",
    description="Backend inicial para Shirley's Customers",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4200",
        "http://localhost:5173",
        "https://shirleys-front.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(customers_router, prefix="/api/customers", tags=["Customers"])


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
        "service": "shirleys-customers",
    }