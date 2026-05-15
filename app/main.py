from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.customers import router as customers_router
from app.staff_auth import router as staff_router
from app.catering import router as catering_router

app = FastAPI(
    title="Shirley's Backend",
    description="Backend para Shirley's Customers y Catering Service",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4200",
        "http://localhost:5173",
        "https://shirleys-front.vercel.app",
        "https://shirleys-frontend.vercel.app",
        "https://shirleyscr.com",
        "https://www.shirleyscr.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# STATIC FILES
app.mount("/static", StaticFiles(directory="static"), name="static")

# CUSTOMERS ROUTES
app.include_router(
    customers_router,
    prefix="/api/customers",
    tags=["Customers"],
)

# STAFF AUTH ROUTES
app.include_router(
    staff_router,
    prefix="/api/staff",
    tags=["Staff"],
)

# CATERING ROUTES
app.include_router(
    catering_router,
    prefix="/api/catering",
    tags=["Catering"],
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
    }