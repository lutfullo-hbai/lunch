from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import engine
from app.main import create_app


@pytest.fixture(scope="session")
def app():
    return create_app()


@pytest.fixture
async def client(app) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def db() -> AsyncIterator[AsyncSession]:
    """Har bir test alohida tranzaksiyada ishlaydi va oxirida rollback qilinadi."""
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(bind=connection, join_transaction_mode="create_savepoint")
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()
