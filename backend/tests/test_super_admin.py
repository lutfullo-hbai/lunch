from pydantic import SecretStr

from app.core.config import get_settings
from app.models.enums import UserRole
from app.services.auth import ensure_super_admin


async def test_super_admin_is_created_once(db, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "super_admin_email", "Boss@Example.com")
    monkeypatch.setattr(settings, "super_admin_password", SecretStr("admin-pass-123"))

    first = await ensure_super_admin(db)
    second = await ensure_super_admin(db)

    assert first is not None and second is not None
    assert first.id == second.id
    assert first.email == "boss@example.com"
    assert first.role is UserRole.ADMIN


async def test_super_admin_skipped_without_env(db, monkeypatch):
    monkeypatch.setattr(get_settings(), "super_admin_email", None)
    assert await ensure_super_admin(db) is None
