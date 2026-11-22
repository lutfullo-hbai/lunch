from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings


def build_engine() -> AsyncEngine:
    settings = get_settings()
    return create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
    )


engine = build_engine()
SessionFactory = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionFactory() as session:
        yield session


# Fon vazifalari (masalan Telegram xabari) so'rov tugagach o'z sessiyasini ochadi.
SessionMaker = Callable[[], AbstractAsyncContextManager[AsyncSession]]


def get_session_maker() -> SessionMaker:
    return SessionFactory
