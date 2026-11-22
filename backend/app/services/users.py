"""Admin uchun userlar: ro'yxat, qidiruv, bloklash."""

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import with_expression

from app.core.errors import cannot_block_admin, user_not_found
from app.db.query import PageResult, contains, paginate
from app.models import Order, User
from app.models.enums import UserRole
from app.schemas.common import PageParams
from app.services.auth import revoke_all_sessions


def _with_orders_count():
    """Userlar `orders_count` (buyurtmalari soni) bilan birga."""
    orders_count = select(func.count(Order.id)).where(Order.user_id == User.id).scalar_subquery()
    return (
        select(User)
        .options(with_expression(User.orders_count, orders_count))
        .execution_options(populate_existing=True)  # sessiyadagi obyektda ham son yangilansin
    )


async def list_users(
    db: AsyncSession,
    page: PageParams,
    search: str | None = None,
    role: UserRole | None = None,
    is_active: bool | None = None,
) -> PageResult[User]:
    query = _with_orders_count()
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

    query = query.order_by(User.created_at.desc(), User.id.desc())
    return await paginate(db, query, page.offset, page.size)


async def get_user(db: AsyncSession, user_id: int) -> User:
    user = await db.scalar(_with_orders_count().where(User.id == user_id))
    if user is None:
        raise user_not_found()
    return user


async def set_status(db: AsyncSession, user_id: int, is_active: bool) -> User:
    """Userni bloklaydi yoki blokdan chiqaradi. Bloklanganda barcha sessiyalari yopiladi."""
    user = await db.get(User, user_id)
    if user is None:
        raise user_not_found()
    if user.role is UserRole.ADMIN:
        raise cannot_block_admin()

    user.is_active = is_active
    if not is_active:
        await revoke_all_sessions(db, user.id)
    await db.commit()
    return await get_user(db, user_id)
