"""Auth biznes logikasi: register, login, token yangilash, logout."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi import status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import (
    create_access_token,
    derive_signing_key,
    hash_password,
    hash_token,
    new_refresh_token,
    verify_password,
)
from app.models import RefreshToken, User
from app.models.enums import UserRole
from app.schemas.auth import LoginIn, RegisterIn


def invalid_credentials() -> AppError:
    return AppError(
        status.HTTP_401_UNAUTHORIZED, "INVALID_CREDENTIALS", "Email yoki parol noto'g'ri"
    )


def invalid_refresh_token() -> AppError:
    return AppError(status.HTTP_401_UNAUTHORIZED, "INVALID_REFRESH_TOKEN", "Refresh token yaroqsiz")


def user_inactive() -> AppError:
    return AppError(status.HTTP_403_FORBIDDEN, "USER_INACTIVE", "Hisob bloklangan")


# Mavjud bo'lmagan email bilan login ham parolni tekshirgandek vaqt olishi uchun
# (javob vaqtidan email bor-yo'qligini bilib bo'lmasin).
_DUMMY_HASH: str | None = None


def _dummy_hash() -> str:
    global _DUMMY_HASH
    if _DUMMY_HASH is None:
        _DUMMY_HASH = hash_password("dummy-password")
    return _DUMMY_HASH


@dataclass(frozen=True)
class IssuedTokens:
    access_token: str
    refresh_token: str
    expires_in: int
    signing_key: str
    user: User


def _now() -> datetime:
    return datetime.now(UTC)


async def _issue_tokens(db: AsyncSession, user: User) -> IssuedTokens:
    raw_refresh = new_refresh_token()
    session = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(raw_refresh),
        expires_at=_now() + timedelta(days=get_settings().refresh_token_ttl_days),
    )
    db.add(session)
    await db.flush()

    access_token, expires_in = create_access_token(user.id, session.jti)
    return IssuedTokens(
        access_token=access_token,
        refresh_token=raw_refresh,
        expires_in=expires_in,
        signing_key=derive_signing_key(session.jti),
        user=user,
    )


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    return await db.scalar(select(User).where(User.email == email.lower()))


async def register(db: AsyncSession, data: RegisterIn) -> IssuedTokens:
    if await get_user_by_email(db, data.email):
        raise AppError(
            status.HTTP_409_CONFLICT, "EMAIL_TAKEN", "Bu email allaqachon ro'yxatdan o'tgan"
        )

    user = User(
        email=data.email,
        full_name=data.full_name,
        password_hash=hash_password(data.password),
        last_login_at=_now(),
    )
    db.add(user)
    await db.flush()
    tokens = await _issue_tokens(db, user)
    await db.commit()
    return tokens


async def login(db: AsyncSession, data: LoginIn) -> IssuedTokens:
    user = await get_user_by_email(db, data.email)
    if user is None:
        verify_password(data.password, _dummy_hash())
        raise invalid_credentials()
    if not verify_password(data.password, user.password_hash):
        raise invalid_credentials()
    if not user.is_active:
        raise user_inactive()

    user.last_login_at = _now()
    tokens = await _issue_tokens(db, user)
    await db.commit()
    return tokens


async def refresh(db: AsyncSession, raw_token: str) -> IssuedTokens:
    """Refresh tokenni almashtiradi (rotation).

    Bekor qilingan token qayta ishlatilsa, u o'g'irlangan deb hisoblanadi va
    userning barcha sessiyalari bekor qilinadi.
    """
    session = await db.scalar(
        select(RefreshToken)
        .where(RefreshToken.token_hash == hash_token(raw_token))
        .with_for_update()  # bir token bilan parallel ikki refresh bo'lmasin
    )
    if session is None:
        raise invalid_refresh_token()

    if session.revoked_at is not None:
        await revoke_all_sessions(db, session.user_id)
        await db.commit()
        raise invalid_refresh_token()

    if session.expires_at <= _now():
        raise invalid_refresh_token()

    user = await db.get(User, session.user_id)
    if user is None or not user.is_active:
        raise user_inactive()

    session.revoked_at = _now()
    tokens = await _issue_tokens(db, user)
    await db.commit()
    return tokens


async def logout(db: AsyncSession, session: RefreshToken) -> None:
    session.revoked_at = _now()
    await db.commit()


async def revoke_all_sessions(db: AsyncSession, user_id: int) -> None:
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=_now())
    )


async def ensure_super_admin(db: AsyncSession) -> User | None:
    """`.env` dagi super adminni yaratadi yoki uni admin holatiga keltiradi."""
    settings = get_settings()
    if not settings.super_admin_email or settings.super_admin_password is None:
        return None

    user = await get_user_by_email(db, settings.super_admin_email)
    if user is None:
        user = User(
            email=settings.super_admin_email.lower(),
            full_name=settings.super_admin_full_name,
            password_hash=hash_password(settings.super_admin_password.get_secret_value()),
        )
        db.add(user)
    user.role = UserRole.ADMIN
    user.is_active = True
    await db.commit()
    return user
