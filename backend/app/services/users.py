"""Admin uchun userlar: ro'yxat, qidiruv, bloklash."""

from fastapi import status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.db.query import contains
from app.models import Order, User
from app.models.enums import UserRole
from app.schemas.common import Page, PageParams
from app.schemas.user import AdminUserOut
from app.services.auth import revoke_all_sessions


def _orders_count():
    return select(func.count(Order.id)).where(Order.user_id == User.id).scalar_subquery()


def _to_out(user: User, orders_count: int) -> AdminUserOut:
    return AdminUserOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        phone=user.phone,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
        orders_count=orders_count,
    )


async def list_users(
    db: AsyncSession,
    page: PageParams,
    search: str | None = None,
    role: UserRole | None = None,
    is_active: bool | None = None,
) -> Page[AdminUserOut]:
    query = select(User)
    if search:
        query = query.where(
            or_(
                contains(User.email, search),
                contains(User.full_name, search),
                contains(User.phone, search),
            )
        )
    if role is not None:
        query = query.where(User.role == role)
    if is_active is not None:
        query = query.where(User.is_active == is_active)

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    rows = await db.execute(
        query.add_columns(_orders_count())
        .order_by(User.created_at.desc(), User.id.desc())
        .offset(page.offset)
        .limit(page.size)
    )
    return Page(
        items=[_to_out(user, count) for user, count in rows.all()],
        total=total or 0,
        page=page.page,
        size=page.size,
    )


async def get_user(db: AsyncSession, user_id: int) -> AdminUserOut:
    row = (await db.execute(select(User, _orders_count()).where(User.id == user_id))).first()
    if row is None:
        raise AppError(status.HTTP_404_NOT_FOUND, "USER_NOT_FOUND", "User topilmadi")
    return _to_out(row[0], row[1])


async def set_status(db: AsyncSession, user_id: int, is_active: bool) -> AdminUserOut:
    """Userni bloklaydi yoki blokdan chiqaradi. Bloklanganda barcha sessiyalari yopiladi."""
    user = await db.get(User, user_id)
    if user is None:
        raise AppError(status.HTTP_404_NOT_FOUND, "USER_NOT_FOUND", "User topilmadi")
    if user.role is UserRole.ADMIN:
        raise AppError(status.HTTP_409_CONFLICT, "CANNOT_BLOCK_ADMIN", "Adminni bloklab bo'lmaydi")

    user.is_active = is_active
    if not is_active:
        await revoke_all_sessions(db, user.id)
    await db.commit()
    return await get_user(db, user_id)
