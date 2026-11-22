from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import NotifyStatus, OrderStatus, PaymentMethod


class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    menu_item_id: int
    name: str = Field(validation_alias="name_snapshot")
    price: Decimal = Field(validation_alias="price_snapshot")
    quantity: int
    subtotal: Decimal


class OrderUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: str


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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
