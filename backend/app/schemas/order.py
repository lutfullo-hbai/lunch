from datetime import datetime
from decimal import Decimal
from typing import Annotated

from annotated_types import Ge
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.config import get_settings
from app.models.enums import NotifyStatus, OrderStatus, PaymentMethod
from app.schemas.types import Id, Int32


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
    notify_status: NotifyStatus
    created_at: datetime
    updated_at: datetime
    items: list[OrderItemOut]
    allowed_statuses: list[OrderStatus]


class OrderLineIn(BaseModel):
    menu_item_id: Id
    # Savatda "-" tugmasi 0 dan pastga tushirmaydi; backend ham 1 dan kamni qabul qilmaydi.
    quantity: Annotated[Int32, Ge(1)]


class OrderCreate(BaseModel):
    items: list[OrderLineIn] = Field(min_length=1)
    payment_method: PaymentMethod

    @field_validator("items")
    @classmethod
    def limit_lines(cls, value: list[OrderLineIn]) -> list[OrderLineIn]:
        max_lines = get_settings().order_max_lines
        if len(value) > max_lines:
            raise ValueError(f"Buyurtmada {max_lines} tadan ko'p ovqat bo'lmasligi kerak")
        return value


class MyOrderOut(BaseModel):
    """User ko'radigan buyurtma."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    status: OrderStatus
    payment_method: PaymentMethod
    total_price: Decimal
    created_at: datetime
    items: list[OrderItemOut]


class OrderStatusUpdate(BaseModel):
    status: OrderStatus
