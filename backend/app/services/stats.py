"""Dashboard ko'rsatkichlari. Kunlar `TIMEZONE` bo'yicha hisoblanadi.

Tushum faqat yetkazilgan buyurtmalardan olinadi (pul shu paytda to'lanadi).
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import ColumnElement, case, func, select
from sqlalchemy.dialects.postgresql import aggregate_order_by
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import Order, OrderItem, User
from app.models.enums import OrderStatus, PaymentMethod, UserRole
from app.schemas.stats import (
    DayStats,
    OrderCounts,
    Revenue,
    StatsOut,
    StatsPeriod,
    TopItem,
    UserCounts,
)

PERIOD_DAYS = {StatsPeriod.TODAY: 1, StatsPeriod.WEEK: 7, StatsPeriod.MONTH: 30}
REVENUE_STATUS = OrderStatus.DELIVERED
OPEN_STATUSES = (OrderStatus.NEW, OrderStatus.ACCEPTED, OrderStatus.READY)
TOP_ITEMS_LIMIT = 5
ZERO = Decimal(0)


def local_today() -> date:
    return datetime.now(get_settings().tz).date()


@dataclass(frozen=True)
class Window:
    """Davr: `date_from` dan `date_to` gacha (ikkalasi ham kiradi), mahalliy kunlar."""

    date_from: date
    date_to: date

    @classmethod
    def ending_today(cls, period: StatsPeriod) -> "Window":
        today = local_today()
        return cls(today - timedelta(days=PERIOD_DAYS[period] - 1), today)

    @property
    def days(self) -> list[date]:
        count = (self.date_to - self.date_from).days + 1
        return [self.date_from + timedelta(days=i) for i in range(count)]

    def contains(self, column) -> ColumnElement[bool]:
        tz = get_settings().tz
        start = datetime.combine(self.date_from, time.min, tzinfo=tz)
        end = datetime.combine(self.date_to + timedelta(days=1), time.min, tzinfo=tz)
        return (column >= start) & (column < end)


def _local_day(column):
    """timestamptz ustunni `TIMEZONE` dagi sanaga aylantiradi (PostgreSQL `timezone()`)."""
    return func.date(func.timezone(get_settings().timezone, column))


async def _order_counts(db: AsyncSession, window: Window) -> OrderCounts:
    rows = await db.execute(
        select(Order.status, func.count())
        .where(window.contains(Order.created_at))
        .group_by(Order.status)
    )
    by_status = dict(rows.all())
    return OrderCounts(
        total=sum(by_status.values()),
        by_status={status: by_status.get(status, 0) for status in OrderStatus},
    )


async def _revenue(db: AsyncSession, window: Window) -> Revenue:
    rows = await db.execute(
        select(Order.payment_method, func.sum(Order.total_price))
        .where(window.contains(Order.created_at), Order.status == REVENUE_STATUS)
        .group_by(Order.payment_method)
    )
    by_payment = dict(rows.all())
    cash = by_payment.get(PaymentMethod.CASH, ZERO)
    card = by_payment.get(PaymentMethod.CARD, ZERO)
    return Revenue(total=cash + card, cash=cash, card=card)


async def _daily(db: AsyncSession, window: Window) -> list[DayStats]:
    day = _local_day(Order.created_at)
    revenue = case((Order.status == REVENUE_STATUS, Order.total_price), else_=ZERO)
    rows = await db.execute(
        select(day, func.count(), func.sum(revenue))
        .where(window.contains(Order.created_at))
        .group_by(day)
    )
    by_day = {row[0]: row for row in rows.all()}
    # Buyurtmasiz kunlar ham 0 bilan qaytadi: grafikda bo'shliq qolmasin.
    return [
        DayStats(date=d, orders=by_day[d][1], revenue=by_day[d][2])
        if d in by_day
        else DayStats(date=d, orders=0, revenue=ZERO)
        for d in window.days
    ]


async def _top_items(db: AsyncSession, window: Window) -> list[TopItem]:
    quantity = func.sum(OrderItem.quantity)
    # Nom buyurtma paytidagidan (snapshot) olinadi, davrdagi eng so'nggi buyurtmadan:
    # keyin ovqat nomi o'zgartirilsa ham, o'tgan davr statistikasi o'zgarmaydi.
    name = func.array_agg(aggregate_order_by(OrderItem.name_snapshot, Order.created_at.desc()))[1]
    rows = await db.execute(
        select(
            OrderItem.menu_item_id,
            name,
            quantity,
            func.sum(OrderItem.price_snapshot * OrderItem.quantity),
        )
        .join(Order, OrderItem.order_id == Order.id)
        .where(window.contains(Order.created_at), Order.status != OrderStatus.CANCELLED)
        .group_by(OrderItem.menu_item_id)
        .order_by(quantity.desc(), OrderItem.menu_item_id)
        .limit(TOP_ITEMS_LIMIT)
    )
    return [
        TopItem(menu_item_id=item_id, name=name, quantity=qty, revenue=amount)
        for item_id, name, qty, amount in rows.all()
    ]


async def _user_counts(db: AsyncSession, window: Window) -> UserCounts:
    customers = select(func.count()).select_from(User).where(User.role == UserRole.USER)
    total = await db.scalar(customers)
    new = await db.scalar(customers.where(window.contains(User.created_at)))
    return UserCounts(total=total or 0, new=new or 0)


async def _pending_orders(db: AsyncSession) -> int:
    """Hozir ochiq buyurtmalar, davrdan qat'i nazar (admin bajarishi kerak bo'lganlar)."""
    count = await db.scalar(
        select(func.count()).select_from(Order).where(Order.status.in_(OPEN_STATUSES))
    )
    return count or 0


async def collect(db: AsyncSession, period: StatsPeriod) -> StatsOut:
    window = Window.ending_today(period)
    return StatsOut(
        period=period,
        date_from=window.date_from,
        date_to=window.date_to,
        orders=await _order_counts(db, window),
        revenue=await _revenue(db, window),
        users=await _user_counts(db, window),
        pending_orders=await _pending_orders(db),
        daily=await _daily(db, window),
        top_items=await _top_items(db, window),
    )
