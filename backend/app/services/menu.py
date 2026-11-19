"""Menyu (ovqatlar): ro'yxat, yaratish, tahrirlash, o'chirish, rasm."""

from datetime import UTC, datetime

from fastapi import UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import AppError
from app.models import Category, MenuItem
from app.schemas.common import Page, PageParams
from app.schemas.menu import MenuItemCreate, MenuItemOut, MenuItemUpdate
from app.services import images

# Bu maydonlar bazada NOT NULL, PATCH'da null yuborilsa e'tiborsiz qoldiriladi.
_REQUIRED_FIELDS = {"category_id", "name", "price", "is_available"}


def to_out(item: MenuItem) -> MenuItemOut:
    return MenuItemOut(
        id=item.id,
        category_id=item.category_id,
        category_name=item.category.name if item.category else None,
        name=item.name,
        description=item.description,
        price=item.price,
        portion=item.portion,
        is_available=item.is_available,
        image_url=images.public_url(item.image_path),
        thumb_url=images.public_url(images.thumb_path(item.image_path))
        if item.image_path
        else None,
    )


def _not_found() -> AppError:
    return AppError(status.HTTP_404_NOT_FOUND, "MENU_ITEM_NOT_FOUND", "Ovqat topilmadi")


def _active_items():
    return (
        select(MenuItem)
        .where(MenuItem.deleted_at.is_(None))
        .options(selectinload(MenuItem.category))
    )


async def _ensure_category_exists(db: AsyncSession, category_id: int) -> None:
    if await db.get(Category, category_id) is None:
        raise AppError(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "CATEGORY_NOT_FOUND", "Kategoriya topilmadi"
        )


async def list_items(
    db: AsyncSession,
    page: PageParams,
    category_id: int | None = None,
    search: str | None = None,
    is_available: bool | None = None,
) -> Page[MenuItemOut]:
    query = _active_items()
    if category_id is not None:
        query = query.where(MenuItem.category_id == category_id)
    if search:
        query = query.where(MenuItem.name.ilike(f"%{search.strip()}%"))
    if is_available is not None:
        query = query.where(MenuItem.is_available == is_available)

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    rows = await db.scalars(
        query.order_by(MenuItem.name, MenuItem.id).offset(page.offset).limit(page.size)
    )
    return Page(items=[to_out(i) for i in rows], total=total or 0, page=page.page, size=page.size)


async def get_item(db: AsyncSession, item_id: int) -> MenuItem:
    item = await db.scalar(_active_items().where(MenuItem.id == item_id))
    if item is None:
        raise _not_found()
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
        raise _not_found()
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
