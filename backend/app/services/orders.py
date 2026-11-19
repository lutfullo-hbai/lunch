"""Buyurtmalar: admin uchun ro'yxat, tafsilot va holatni o'zgartirish."""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from fastapi import status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.errors import AppError
from app.models import Order
from app.models.enums import OrderStatus, PaymentMethod
from app.schemas.common import Page, PageParams
from app.schemas.order import OrderItemOut, OrderOut, OrderUserOut

# Holatlar faqat oldinga yuradi. Yetkazilgan yoki bekor qilingan buyurtma yopiq.
STATUS_TRANSITIONS: dict[OrderStatus, frozenset[OrderStatus]] = {
    OrderStatus.NEW: frozenset({OrderStatus.ACCEPTED, OrderStatus.CANCELLED}),
    OrderStatus.ACCEPTED: frozenset({OrderStatus.READY, OrderStatus.CANCELLED}),
    OrderStatus.READY: frozenset({OrderStatus.DELIVERED, OrderStatus.CANCELLED}),
    OrderStatus.DELIVERED: frozenset(),
    OrderStatus.CANCELLED: frozenset(),
}


@dataclass(frozen=True)
class OrderFilters:
    status: OrderStatus | None = None
    payment_method: PaymentMethod | None = None
    user_id: int | None = None
    date_from: date | None = None
    date_to: date | None = None


def _allowed_next(current: OrderStatus) -> list[OrderStatus]:
    # Enum tartibida qaytaramiz, javob har doim bir xil bo'lsin.
    return [s for s in OrderStatus if s in STATUS_TRANSITIONS[current]]


def to_out(order: Order) -> OrderOut:
    return OrderOut(
        id=order.id,
        user=OrderUserOut(id=order.user.id, full_name=order.user.full_name, email=order.user.email),
        status=order.status,
        payment_method=order.payment_method,
        total_price=order.total_price,
        phone=order.phone,
        address=order.address,
        comment=order.comment,
        notify_status=order.notify_status,
        created_at=order.created_at,
        updated_at=order.updated_at,
        items=[
            OrderItemOut(
                menu_item_id=item.menu_item_id,
                name=item.name_snapshot,
                price=item.price_snapshot,
                quantity=item.quantity,
                subtotal=item.price_snapshot * item.quantity,
            )
            for item in order.items
        ],
        allowed_statuses=_allowed_next(order.status),
    )


def _start_of_day(day: date) -> datetime:
    """Mahalliy kun boshini (TIMEZONE bo'yicha) timezone-aware datetime qiladi."""
    return datetime.combine(day, time.min, tzinfo=get_settings().tz)


def _base_query():
    return select(Order).options(selectinload(Order.items), selectinload(Order.user))


async def list_orders(db: AsyncSession, page: PageParams, filters: OrderFilters) -> Page[OrderOut]:
    query = _base_query()
    if filters.status is not None:
        query = query.where(Order.status == filters.status)
    if filters.payment_method is not None:
        query = query.where(Order.payment_method == filters.payment_method)
    if filters.user_id is not None:
        query = query.where(Order.user_id == filters.user_id)
    if filters.date_from is not None:
        query = query.where(Order.created_at >= _start_of_day(filters.date_from))
    if filters.date_to is not None:
        query = query.where(Order.created_at < _start_of_day(filters.date_to + timedelta(days=1)))

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    rows = await db.scalars(
        query.order_by(Order.created_at.desc(), Order.id.desc())
        .offset(page.offset)
        .limit(page.size)
    )
    return Page(items=[to_out(o) for o in rows], total=total or 0, page=page.page, size=page.size)


async def get_order(db: AsyncSession, order_id: int) -> Order:
    order = await db.scalar(_base_query().where(Order.id == order_id))
    if order is None:
        raise AppError(status.HTTP_404_NOT_FOUND, "ORDER_NOT_FOUND", "Buyurtma topilmadi")
    return order


async def change_status(db: AsyncSession, order_id: int, new_status: OrderStatus) -> Order:
    # Ikki admin bir vaqtda o'zgartirsa, ikkinchisi birinchisining natijasini ko'radi.
    order = await db.scalar(_base_query().where(Order.id == order_id).with_for_update(of=Order))
    if order is None:
        raise AppError(status.HTTP_404_NOT_FOUND, "ORDER_NOT_FOUND", "Buyurtma topilmadi")
    if new_status not in STATUS_TRANSITIONS[order.status]:
        raise AppError(
            status.HTTP_409_CONFLICT,
            "INVALID_STATUS_TRANSITION",
            f"Buyurtma holatini '{order.status}' dan '{new_status}' ga o'zgartirib bo'lmaydi",
            details={"current": order.status, "allowed": _allowed_next(order.status)},
        )
    order.status = new_status
    await db.commit()
    db.expire_all()
    return await get_order(db, order_id)
