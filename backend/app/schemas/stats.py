from datetime import date
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel

from app.models.enums import OrderStatus


class StatsPeriod(StrEnum):
    TODAY = "today"
    WEEK = "7d"
    MONTH = "30d"


class OrderCounts(BaseModel):
    total: int
    by_status: dict[OrderStatus, int]


class Revenue(BaseModel):
    total: Decimal
    cash: Decimal
    card: Decimal


class UserCounts(BaseModel):
    total: int
    new: int


class DayStats(BaseModel):
    date: date
    orders: int
    revenue: Decimal


class TopItem(BaseModel):
    menu_item_id: int
    name: str
    quantity: int
    revenue: Decimal


class StatsOut(BaseModel):
    period: StatsPeriod
    date_from: date
    date_to: date
    orders: OrderCounts
    revenue: Revenue
    users: UserCounts
    pending_orders: int
    daily: list[DayStats]
    top_items: list[TopItem]
