"""User ko'radigan menyu: faqat faol kategoriyalar va sotuvdagi ovqatlar."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import contains_eager

from app.core.errors import menu_item_not_found
from app.models import Category, MenuItem


def _orderable_items():
    """Buyurtma qilish mumkin bo'lgan ovqatlar: o'chirilmagan, sotuvda, kategoriyasi faol."""
    return (
        select(MenuItem)
        .join(MenuItem.category)
        .where(
            MenuItem.deleted_at.is_(None),
            MenuItem.is_available.is_(True),
            Category.is_active.is_(True),
        )
        .options(contains_eager(MenuItem.category))
    )


async def list_categories(db: AsyncSession) -> list[Category]:
    rows = await db.scalars(
        select(Category)
        .where(Category.is_active.is_(True))
        .order_by(Category.sort_order, Category.name)
    )
    return list(rows)


async def list_items(db: AsyncSession, category_id: int | None = None) -> list[MenuItem]:
    query = _orderable_items()
    if category_id is not None:
        query = query.where(MenuItem.category_id == category_id)
    rows = await db.scalars(query.order_by(Category.sort_order, MenuItem.name, MenuItem.id))
    return list(rows)


async def get_item(db: AsyncSession, item_id: int) -> MenuItem:
    item = await db.scalar(_orderable_items().where(MenuItem.id == item_id))
    if item is None:
        raise menu_item_not_found()
    return item

