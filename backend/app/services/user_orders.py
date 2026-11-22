"""User buyurtmalari: yaratish."""

from collections import Counter
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import items_unavailable, order_not_found, validation_error
from app.models import Order, OrderItem, User
from app.schemas.order import OrderCreate
from app.services import catalog

# Jami summa bazadagi ustunga sig'ishi kerak (NUMERIC(precision, scale)).
_TOTAL_TYPE = Order.__table__.c.total_price.type
MAX_TOTAL = Decimal(10) ** (_TOTAL_TYPE.precision - _TOTAL_TYPE.scale)


async def get_order(db: AsyncSession, user: User, order_id: int) -> Order:
    """Faqat userning o'z buyurtmasi. Boshqaniki ham "topilmadi" (borligi bilinmasin)."""
    order = await db.scalar(
        select(Order)
        .where(Order.id == order_id, Order.user_id == user.id)
        .options(selectinload(Order.items))
        .execution_options(populate_existing=True)
    )
    if order is None:
        raise order_not_found()
    return order


async def create_order(db: AsyncSession, user: User, data: OrderCreate) -> Order:
    """Narx va nom bazadan olinadi, mijoz yuborgan narxga ishonilmaydi.

    Savatdagi bir xil ovqatlar bitta qatorga birlashtiriladi.
    """
    quantities: Counter[int] = Counter()
    for line in data.items:
        quantities[line.menu_item_id] += line.quantity

    items = await catalog.get_items_by_ids(db, set(quantities))
    missing = sorted(set(quantities) - set(items))
    if missing:
        raise items_unavailable(missing)

    lines = [
        OrderItem(
            menu_item_id=item_id,
            name_snapshot=items[item_id].name,
            price_snapshot=items[item_id].price,
            quantity=quantity,
        )
        for item_id, quantity in quantities.items()
    ]
    total = sum((line.price_snapshot * line.quantity for line in lines), Decimal(0))
    if total >= MAX_TOTAL:
        raise validation_error("items", "Buyurtma summasi juda katta")

    order = Order(
        user_id=user.id, total_price=total, payment_method=data.payment_method, items=lines
    )
    db.add(order)
    await db.commit()
    return await get_order(db, user, order.id)
