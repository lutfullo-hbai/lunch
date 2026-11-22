"""Menyu (ovqatlar): ro'yxat, yaratish, tahrirlash, o'chirish, rasm."""

from datetime import UTC, datetime

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import menu_item_not_found, validation_error
from app.db.query import PageResult, contains, paginate
from app.models import Category, MenuItem
from app.schemas.common import PageParams
from app.schemas.menu import MenuItemCreate, MenuItemUpdate
from app.services import images

# Bu maydonlar bazada NOT NULL, PATCH'da null yuborilsa e'tiborsiz qoldiriladi.
_REQUIRED_FIELDS = {"category_id", "name", "price", "is_available"}


def _active_items():
    return (
        select(MenuItem)
        .where(MenuItem.deleted_at.is_(None))
        .options(selectinload(MenuItem.category))
    )


async def _ensure_category_exists(db: AsyncSession, category_id: int) -> None:
    if await db.get(Category, category_id) is None:
        raise validation_error("category_id", "Kategoriya topilmadi")


async def list_items(
    db: AsyncSession,
    page: PageParams,
    category_id: int | None = None,
    search: str | None = None,
    is_available: bool | None = None,
) -> PageResult[MenuItem]:
    query = _active_items()
    if category_id is not None:
        query = query.where(MenuItem.category_id == category_id)
    if search:
        query = query.where(contains(MenuItem.name, search))
    if is_available is not None:
        query = query.where(MenuItem.is_available == is_available)

    query = query.order_by(MenuItem.name, MenuItem.id)
    return await paginate(db, query, page.offset, page.size)


async def get_item(db: AsyncSession, item_id: int) -> MenuItem:
    item = await db.scalar(_active_items().where(MenuItem.id == item_id))
    if item is None:
        raise menu_item_not_found()
    return item


async def _reload(db: AsyncSession, item_id: int) -> MenuItem:
    db.expire_all()
    return await get_item(db, item_id)


async def create_item(db: AsyncSession, data: MenuItemCreate) -> MenuItem:
    await _ensure_category_exists(db, data.category_id)
    item = MenuItem(**data.model_dump())
    db.add(item)
    await db.commit()
    return await _reload(db, item.id)


async def update_item(db: AsyncSession, item_id: int, data: MenuItemUpdate) -> MenuItem:
    item = await get_item(db, item_id)
    changes = {
        field: value
        for field, value in data.model_dump(exclude_unset=True).items()
        if value is not None or field not in _REQUIRED_FIELDS
    }
    if "category_id" in changes:
        await _ensure_category_exists(db, changes["category_id"])
    for field, value in changes.items():
        setattr(item, field, value)
    await db.commit()
    return await _reload(db, item_id)


async def delete_item(db: AsyncSession, item_id: int) -> None:
    """Soft delete: eski buyurtmalar ovqatga havolani yo'qotmasligi uchun."""
    item = await get_item(db, item_id)
    item.deleted_at = datetime.now(UTC)
    item.is_available = False
    await db.commit()


async def _lock_item(db: AsyncSession, item_id: int) -> MenuItem:
    """Rasm almashtirishda qatorni qulflaydi: parallel ikki yuklash eski faylni
    ikki marta o'chirib, yangisini yetim qoldirmasin."""
    item = await db.scalar(
        select(MenuItem)
        .where(MenuItem.id == item_id, MenuItem.deleted_at.is_(None))
        .with_for_update()
    )
    if item is None:
        raise menu_item_not_found()
    return item


async def set_image(db: AsyncSession, item_id: int, upload: UploadFile) -> MenuItem:
    await get_item(db, item_id)  # yo'q bo'lsa rasmni bekorga ishlamaslik uchun
    # Rasm qulfdan oldin qayta ishlanadi: og'ir ish paytida qator band turmasin.
    new_path = await images.save_menu_image(upload)
    try:
        item = await _lock_item(db, item_id)
    except Exception:
        images.delete_image(new_path)
        raise
    old_path, item.image_path = item.image_path, new_path
    try:
        await db.commit()
    except Exception:
        images.delete_image(new_path)
        raise
    images.delete_image(old_path)
    return await _reload(db, item_id)


async def remove_image(db: AsyncSession, item_id: int) -> MenuItem:
    item = await _lock_item(db, item_id)
    old_path, item.image_path = item.image_path, None
    await db.commit()
    images.delete_image(old_path)
    return await _reload(db, item_id)
