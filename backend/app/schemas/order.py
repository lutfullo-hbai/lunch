from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.models.enums import NotifyStatus, OrderStatus, PaymentMethod


class OrderItemOut(BaseModel):
    menu_item_id: int
    name: str
    price: Decimal
    quantity: int
    subtotal: Decimal


class OrderUserOut(BaseModel):
    id: int
    full_name: str
    email: str


class OrderOut(BaseModel):
    id: int
    user: OrderUserOut
    status: OrderStatus
    payment_method: PaymentMethod
    total_price: Decimal
    phone: str
    address: str
    comment: str | None
    notify_status: NotifyStatus
    created_at: datetime
    updated_at: datetime
    items: list[OrderItemOut]
    allowed_statuses: list[OrderStatus]


class OrderStatusUpdate(BaseModel):
    status: OrderStatus
