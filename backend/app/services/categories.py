"""Kategoriyalar: ro'yxat, yaratish, tahrirlash, o'chirish."""

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import with_expression

from app.core.errors import category_exists, category_not_empty, category_not_found
from app.models import Category, MenuItem
from app.schemas.category import CategoryCreate, CategoryUpdate


def _with_items_count():
    """Kategoriyalar `items_count` (o'chirilmagan ovqatlar soni) bilan birga."""
    items_count = (
        select(func.count(MenuItem.id))
        .where(MenuItem.category_id == Category.id, MenuItem.deleted_at.is_(None))
        .scalar_subquery()
    )
    return (
        select(Category)
        .options(with_expression(Category.items_count, items_count))
        .execution_options(populate_existing=True)  # sessiyadagi obyektda ham son yangilansin
    )


async def list_categories(db: AsyncSession) -> list[Category]:
    rows = await db.scalars(_with_items_count().order_by(Category.sort_order, Category.name))
    return list(rows)


async def get_category(db: AsyncSession, category_id: int) -> Category:
    category = await db.scalar(_with_items_count().where(Category.id == category_id))
    if category is None:
        raise category_not_found()
    return category


async def _ensure_name_free(db: AsyncSession, name: str, exclude_id: int | None = None) -> None:
    query = select(Category.id).where(func.lower(Category.name) == name.lower())
    if exclude_id is not None:
        query = query.where(Category.id != exclude_id)
    if await db.scalar(query):
        raise category_exists()


async def _commit_or_name_taken(db: AsyncSession) -> None:
    """Bir vaqtdagi ikki so'rov tekshiruvdan o'tib ketsa, baza indeksi ushlaydi."""
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise category_exists() from exc


async def create_category(db: AsyncSession, data: CategoryCreate) -> Category:
    await _ensure_name_free(db, data.name)
    category = Category(**data.model_dump())
    db.add(category)
    await _commit_or_name_taken(db)
    return await get_category(db, category.id)


async def update_category(db: AsyncSession, category_id: int, data: CategoryUpdate) -> Category:
    category = await get_category(db, category_id)
    changes = data.model_dump(exclude_unset=True, exclude_none=True)
    if "name" in changes:
        await _ensure_name_free(db, changes["name"], exclude_id=category_id)
    for field, value in changes.items():
        setattr(category, field, value)
    await _commit_or_name_taken(db)
    return await get_category(db, category_id)


async def delete_category(db: AsyncSession, category_id: int) -> None:
    category = await get_category(db, category_id)
    if category.items_count:
        raise category_not_empty(category.items_count)
    await db.delete(category)
    await db.commit()
