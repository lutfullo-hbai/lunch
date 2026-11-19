"""Kategoriyalar: ro'yxat, yaratish, tahrirlash, o'chirish."""

from dataclasses import dataclass

from fastapi import status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models import Category, MenuItem
from app.schemas.category import CategoryCreate, CategoryUpdate


@dataclass(frozen=True)
class CategoryWithCount:
    category: Category
    items_count: int


def _not_found() -> AppError:
    return AppError(status.HTTP_404_NOT_FOUND, "CATEGORY_NOT_FOUND", "Kategoriya topilmadi")


def _name_taken() -> AppError:
    return AppError(status.HTTP_409_CONFLICT, "CATEGORY_EXISTS", "Bu nomli kategoriya bor")


def _active_items_count():
    """Kategoriyadagi o'chirilmagan ovqatlar soni (subquery)."""
    return (
        select(func.count(MenuItem.id))
        .where(MenuItem.category_id == Category.id, MenuItem.deleted_at.is_(None))
        .scalar_subquery()
    )


async def list_categories(db: AsyncSession) -> list[CategoryWithCount]:
    rows = await db.execute(
        select(Category, _active_items_count()).order_by(Category.sort_order, Category.name)
    )
    return [CategoryWithCount(category, count) for category, count in rows.all()]


async def get_category(db: AsyncSession, category_id: int) -> CategoryWithCount:
    row = (
        await db.execute(select(Category, _active_items_count()).where(Category.id == category_id))
    ).first()
    if row is None:
        raise _not_found()
    return CategoryWithCount(row[0], row[1])


async def _ensure_name_free(db: AsyncSession, name: str, exclude_id: int | None = None) -> None:
    query = select(Category.id).where(func.lower(Category.name) == name.lower())
    if exclude_id is not None:
        query = query.where(Category.id != exclude_id)
    if await db.scalar(query):
        raise _name_taken()


async def _commit_or_name_taken(db: AsyncSession) -> None:
    """Bir vaqtdagi ikki so'rov tekshiruvdan o'tib ketsa, baza indeksi ushlaydi."""
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise _name_taken() from exc


async def create_category(db: AsyncSession, data: CategoryCreate) -> CategoryWithCount:
    await _ensure_name_free(db, data.name)
    category = Category(**data.model_dump())
    db.add(category)
    await _commit_or_name_taken(db)
    return CategoryWithCount(category, 0)


async def update_category(
    db: AsyncSession, category_id: int, data: CategoryUpdate
) -> CategoryWithCount:
    current = await get_category(db, category_id)
    changes = data.model_dump(exclude_unset=True, exclude_none=True)
    if "name" in changes:
        await _ensure_name_free(db, changes["name"], exclude_id=category_id)
    for field, value in changes.items():
        setattr(current.category, field, value)
    await _commit_or_name_taken(db)
    return current


async def delete_category(db: AsyncSession, category_id: int) -> None:
    current = await get_category(db, category_id)
    if current.items_count:
        raise AppError(
            status.HTTP_409_CONFLICT,
            "CATEGORY_NOT_EMPTY",
            "Kategoriyada ovqatlar bor. Avval ularni o'chiring yoki boshqa kategoriyaga o'tkazing",
            details={"items_count": current.items_count},
        )
    await db.delete(current.category)
    await db.commit()
