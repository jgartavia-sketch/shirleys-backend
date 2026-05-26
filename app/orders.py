from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Literal
from datetime import datetime
import os
import json
import uuid
import psycopg2
import psycopg2.extras

router = APIRouter()

DATABASE_URL = os.getenv("DATABASE_URL")


def get_connection():
    if not DATABASE_URL:
        raise HTTPException(
            status_code=500,
            detail="DATABASE_URL no está configurado en el servidor.",
        )

    return psycopg2.connect(
        DATABASE_URL,
        cursor_factory=psycopg2.extras.RealDictCursor,
    )


def initialize_orders_table():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS whatsapp_orders (
            id TEXT PRIMARY KEY,
            customer_name TEXT,
            customer_phone TEXT,
            order_type TEXT NOT NULL,
            location_text TEXT,
            items_json TEXT NOT NULL,
            food_total NUMERIC NOT NULL,
            packaging_total NUMERIC NOT NULL,
            total NUMERIC NOT NULL,
            status TEXT NOT NULL,
            notes TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            confirmed_at TEXT
        )
        """
    )

    conn.commit()
    cursor.close()
    conn.close()


class OrderItem(BaseModel):
    name: str
    quantity: int
    price: float


class CreateOrderRequest(BaseModel):
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    order_type: Literal["pickup", "express"]
    location_text: Optional[str] = None
    items: List[OrderItem]
    food_total: float
    packaging_total: float
    total: float


@router.post("/")
def create_order(data: CreateOrderRequest):
    initialize_orders_table()

    conn = get_connection()
    cursor = conn.cursor()

    order_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    cursor.execute(
        """
        INSERT INTO whatsapp_orders (
            id,
            customer_name,
            customer_phone,
            order_type,
            location_text,
            items_json,
            food_total,
            packaging_total,
            total,
            status,
            notes,
            created_at,
            updated_at,
            confirmed_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            order_id,
            data.customer_name,
            data.customer_phone,
            data.order_type,
            data.location_text,
            json.dumps([item.dict() for item in data.items]),
            data.food_total,
            data.packaging_total,
            data.total,
            "pending_confirmation",
            None,
            now,
            now,
            None,
        ),
    )

    conn.commit()
    cursor.close()
    conn.close()

    return {
        "success": True,
        "message": "Order created successfully",
        "order_id": order_id,
        "status": "pending_confirmation",
    }