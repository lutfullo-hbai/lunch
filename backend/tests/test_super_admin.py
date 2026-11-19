import pytest
from pydantic import SecretStr

from app.core.config import get_settings
from app.core.security import verify_password
from app.models import User
from app.models.enums import UserRole
from app.services.auth import SuperAdminEmailTakenError, ensure_super_admin

ADMIN_PASSWORD = "admin-pass-123"


@pytest.fixture
def admin_env(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "super_admin_email", "Boss@Example.com")
    monkeypatch.setattr(settings, "super_admin_password", SecretStr(ADMIN_PASSWORD))


async def test_super_admin_is_created_once(db, admin_env):
    first = await ensure_super_admin(db)
    second = await ensure_super_admin(db)

    assert first is not None and second is not None
    assert first.id == second.id
    assert first.email == "boss@example.com"
    assert first.role is UserRole.ADMIN
    assert verify_password(ADMIN_PASSWORD, first.password_hash)


async def test_preregistered_user_is_not_promoted(db, admin_env):
    intruder = User(email="boss@example.com", password_hash="hujumchi-paroli", full_name="X")
    db.add(intruder)
    await db.flush()

    with pytest.raises(SuperAdminEmailTakenError):
        await ensure_super_admin(db)
    await db.refresh(intruder)
    assert intruder.role is UserRole.USER


async def test_super_admin_skipped_without_env(db, monkeypatch):
    monkeypatch.setattr(get_settings(), "super_admin_email", None)
    assert await ensure_super_admin(db) is None
