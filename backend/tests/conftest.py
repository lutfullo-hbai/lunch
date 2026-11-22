import os

# Test sozlamalari app import qilinishidan oldin o'rnatiladi.
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("JWT_SECRET", "test-secret-" + "x" * 32)
os.environ.setdefault("SIGNING_SECRET", "test-signing-secret-" + "y" * 32)
os.environ.setdefault("BCRYPT_ROUNDS", "4")  # testlar tez ishlashi uchun
# Testlar bitta IP'dan ko'p login/register qiladi. Limit alohida testda tekshiriladi.
os.environ.setdefault("LOGIN_RATE_LIMIT", "100000")
os.environ.setdefault("REGISTER_RATE_LIMIT", "100000")
os.environ.setdefault("ORDER_RATE_LIMIT", "100000")

from collections.abc import AsyncIterator  # noqa: E402
from contextlib import asynccontextmanager  # noqa: E402

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.db.session import engine, get_db, get_session_maker  # noqa: E402
from app.main import create_app  # noqa: E402


@pytest.fixture(scope="session")
def app():
    return create_app()


@pytest.fixture
async def db() -> AsyncIterator[AsyncSession]:
    """Har bir test alohida tranzaksiyada ishlaydi va oxirida rollback qilinadi.

    Ilova ichidagi commit'lar savepoint'ga aylanadi, shuning uchun baza toza qoladi.
    """
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(
            bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
        )
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()


@pytest.fixture
async def client(app, db) -> AsyncIterator[AsyncClient]:
    app.dependency_overrides[get_db] = lambda: db

    @asynccontextmanager
    async def shared_session():
        yield db  # fon vazifalari ham test tranzaksiyasini ko'rsin

    app.dependency_overrides[get_session_maker] = lambda: shared_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


LIVE_EMAIL_DOMAIN = "concurrency.example.com"


@pytest.fixture
async def live_client(app) -> AsyncIterator[AsyncClient]:
    """Haqiqiy commit va lock'lar bilan ishlaydigan client (concurrency testlari uchun).

    Har bir so'rov o'z sessiyasini oladi. Test oxirida `@LIVE_EMAIL_DOMAIN` userlari o'chiriladi.
    """
    from sqlalchemy import delete, select

    from app.db.session import SessionFactory
    from app.models import Order, User

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    async with SessionFactory() as session:
        live_users = select(User.id).where(User.email.like(f"%@{LIVE_EMAIL_DOMAIN}"))
        await session.execute(delete(Order).where(Order.user_id.in_(live_users)))
        await session.execute(delete(User).where(User.id.in_(live_users)))
        await session.commit()
