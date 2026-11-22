"""Buyurtmalar: admin uchun ro'yxat, tafsilot va holatni o'zgartirish."""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.errors import (
    invalid_status_transition,
    order_already_notified,
    order_not_found,
    telegram_not_configured,
)
from app.db.query import PageResult, paginate
from app.models import Order
from app.models.enums import NotifyStatus, OrderStatus, PaymentMethod
from app.models.order import STATUS_TRANSITIONS
from app.schemas.common import PageParams
from app.services import telegram


@dataclass(frozen=True)
class OrderFilters:
    status: OrderStatus | None = None
    payment_method: PaymentMethod | None = None
    user_id: int | None = None
    date_from: date | None = None
    date_to: date | None = None
    notify_status: NotifyStatus | None = None


def _start_of_day(day: date) -> datetime:
    """Mahalliy kun boshini (TIMEZONE bo'yicha) timezone-aware datetime qiladi."""
    return datetime.combine(day, time.min, tzinfo=get_settings().tz)


def _base_query():
    return select(Order).options(selectinload(Order.items), selectinload(Order.user))


async def list_orders(
    db: AsyncSession, page: PageParams, filters: OrderFilters
) -> PageResult[Order]:
    query = _base_query()
    if filters.status is not None:
        query = query.where(Order.status == filters.status)
    if filters.payment_method is not None:
        query = query.where(Order.payment_method == filters.payment_method)
    if filters.user_id is not None:
        query = query.where(Order.user_id == filters.user_id)
    if filters.notify_status is not None:
        query = query.where(Order.notify_status == filters.notify_status)
    # Chekka sanalarda (date.min, date.max) filtr kerak emas va UTC'ga o'tkazib bo'lmaydi:
    # mahalliy vaqt zonasi siljishi 1-yildan oldinga yoki 9999-yildan keyinga chiqaradi.
    if filters.date_from is not None and filters.date_from > date.min:
        query = query.where(Order.created_at >= _start_of_day(filters.date_from))
    if filters.date_to is not None and filters.date_to < date.max:
        query = query.where(Order.created_at < _start_of_day(filters.date_to + timedelta(days=1)))

    query = query.order_by(Order.created_at.desc(), Order.id.desc())
    return await paginate(db, query, page.offset, page.size)


async def get_order(db: AsyncSession, order_id: int) -> Order:
    order = await db.scalar(_base_query().where(Order.id == order_id))
    if order is None:
        raise order_not_found()
    return order


async def set_status(db: AsyncSession, order_id: int, new_status: OrderStatus) -> Order:
    # Ikki admin bir vaqtda o'zgartirsa, ikkinchisi birinchisining natijasini ko'radi.
    order = await db.scalar(_base_query().where(Order.id == order_id).with_for_update(of=Order))
    if order is None:
        raise order_not_found()
    if new_status not in STATUS_TRANSITIONS[order.status]:
        raise invalid_status_transition(order.status, new_status, order.allowed_statuses)
    order.status = new_status
    await db.commit()
    db.expire_all()
    return await get_order(db, order_id)


async def prepare_resend(db: AsyncSession, order_id: int) -> Order:
    """Guruhga yuborilmagan (failed yoki pending) buyurtmani qayta yuborishga tayyorlaydi.

    Yuborishning o'zi fonda bo'ladi; holat `pending` ga qaytadi va natija bilan yangilanadi.
    """
    if not telegram.is_configured():
        raise telegram_not_configured()
    order = await db.scalar(
        _base_query()
        .where(Order.id == order_id)
        .with_for_update(of=Order)
        .execution_options(populate_existing=True)
    )
    if order is None:
        raise order_not_found()
    if order.notify_status is NotifyStatus.SENT:
        raise order_already_notified()
    order.notify_status = NotifyStatus.PENDING
    await db.commit()
    return await get_order(db, order_id)
