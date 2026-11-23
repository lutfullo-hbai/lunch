"""Auth biznes logikasi: register, login, token yangilash, logout."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import (
    email_taken,
    invalid_credentials,
    invalid_refresh_token,
    refresh_token_rotated,
    user_inactive,
    validation_error,
)
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
from app.schemas.auth import ChangePasswordIn, LoginIn, RegisterIn

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
    session_id: uuid.UUID
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
        session_id=session.jti,
        user=user,
    )


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    return await db.scalar(select(User).where(func.lower(User.email) == email.lower()))


async def register(db: AsyncSession, data: RegisterIn) -> IssuedTokens:
    if await get_user_by_email(db, data.email):
        raise email_taken()

    user = User(
        email=data.email,
        full_name=data.full_name,
        password_hash=hash_password(data.password),
        last_login_at=_now(),
    )
    db.add(user)
    try:
        # Bir emailga parallel ikki so'rov: tekshiruvdan ikkalasi o'tsa, indeks ushlaydi.
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise email_taken() from exc
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

    Almashtirilgan (rotated) token qayta ishlatilsa, u o'g'irlangan deb hisoblanadi va
    userning barcha sessiyalari bekor qilinadi. Istisno: token hozirgina (grace oynasi
    ichida) almashtirilgan bo'lsa, bu parallel so'rov, sessiyalar yopilmaydi.
    Logout qilingan token shunchaki rad etiladi: boshqa qurilmalar chiqib ketmasin.
    """
    token_hash = hash_token(raw_token)
    user_id = await db.scalar(
        select(RefreshToken.user_id).where(RefreshToken.token_hash == token_hash)
    )
    if user_id is None:
        raise invalid_refresh_token()

    # Qulflar hamma joyda bir xil tartibda olinadi: avval user, keyin sessiya.
    # User qulfi refresh'ni bloklash va "barcha sessiyalarni yopish" bilan ketma-ket
    # qiladi: aks holda ular orasida yaratilgan yangi sessiya ochiq qolib ketardi.
    user = await lock_user(db, user_id)
    session = await db.scalar(
        select(RefreshToken)
        .where(RefreshToken.token_hash == token_hash)
        .with_for_update()  # bir token bilan parallel ikki refresh bo'lmasin
        .execution_options(populate_existing=True)
    )
    if user is None or session is None:
        raise invalid_refresh_token()

    if session.revoked_at is not None:
        if session.replaced_by_jti is None:  # logout qilingan
            raise invalid_refresh_token()
        if _recently_rotated(session):
            raise refresh_token_rotated()
        await revoke_all_sessions(db, session.user_id)
        await db.commit()
        raise invalid_refresh_token()

    if session.expires_at <= _now():
        raise invalid_refresh_token()

    if not user.is_active:
        raise user_inactive()

    session.revoked_at = _now()
    tokens = await _issue_tokens(db, user)
    session.replaced_by_jti = tokens.session_id
    await db.commit()
    return tokens


async def lock_user(db: AsyncSession, user_id: int) -> User | None:
    """Userni FOR UPDATE bilan qulflaydi. Sessiyalarni o'zgartiradigan joylar shundan boshlanadi."""
    return await db.scalar(
        select(User)
        .where(User.id == user_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def _recently_rotated(session: RefreshToken) -> bool:
    grace = timedelta(seconds=get_settings().refresh_reuse_grace_seconds)
    return _now() - session.revoked_at <= grace


async def logout(db: AsyncSession, session: RefreshToken) -> None:
    session.revoked_at = _now()
    await db.commit()


async def revoke_all_sessions(
    db: AsyncSession, user_id: int, keep: uuid.UUID | None = None
) -> None:
    """Userning barcha ochiq sessiyalarini yopadi (`keep` dan tashqari)."""
    query = update(RefreshToken).where(
        RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None)
    )
    if keep is not None:
        query = query.where(RefreshToken.jti != keep)
    await db.execute(query.values(revoked_at=_now()))


async def change_password(
    db: AsyncSession, user: User, session: RefreshToken, data: ChangePasswordIn
) -> None:
    """Parolni almashtiradi va boshqa qurilmalardagi sessiyalarni yopadi.

    Joriy sessiya qoladi: user shu qurilmada tizimdan chiqib ketmaydi.
    """
    # Refresh bilan bir xil tartibda qulflanadi (avval user), poyga bo'lmasin.
    locked = await lock_user(db, user.id)
    if locked is None or not verify_password(data.current_password, locked.password_hash):
        raise validation_error("current_password", "Joriy parol noto'g'ri")
    if data.new_password == data.current_password:
        raise validation_error("new_password", "Yangi parol joriy paroldan farq qilsin")
    locked.password_hash = hash_password(data.new_password)
    await revoke_all_sessions(db, locked.id, keep=session.jti)
    await db.commit()


async def delete_stale_sessions(db: AsyncSession) -> int:
    """Muddati o'tgan yoki bekor qilinganiga TOKEN_RETENTION_DAYS bo'lgan sessiyalarni o'chiradi.

    Bekor qilingan qatorlar darhol o'chirilmaydi: ular token qayta ishlatilishini
    (o'g'irlikni) aniqlash uchun kerak.
    """
    cutoff = _now() - timedelta(days=get_settings().token_retention_days)
    result = await db.execute(
        delete(RefreshToken).where(
            or_(RefreshToken.expires_at < cutoff, RefreshToken.revoked_at < cutoff)
        )
    )
    await db.commit()
    return result.rowcount or 0


class SuperAdminEmailTakenError(Exception):
    """SUPER_ADMIN_EMAIL oddiy (admin bo'lmagan) userga tegishli."""


async def ensure_super_admin(db: AsyncSession) -> User | None:
    """`.env` dagi super adminni faqat yangi akkaunt sifatida yaratadi.

    Shu email bilan oddiy user allaqachon bo'lsa, u admin qilinmaydi: email
    tasdiqlanmaydi, demak uni begona odam oldindan ro'yxatdan o'tkazgan bo'lishi mumkin.
    """
    settings = get_settings()
    if not settings.super_admin_email or settings.super_admin_password is None:
        return None

    user = await get_user_by_email(db, settings.super_admin_email)
    if user is not None:
        if user.role is not UserRole.ADMIN:
            raise SuperAdminEmailTakenError(settings.super_admin_email)
        return user  # oldingi ishga tushishda yaratilgan, o'zgartirilmaydi

    user = User(
        email=settings.super_admin_email.lower(),
        full_name=settings.super_admin_full_name,
        password_hash=hash_password(settings.super_admin_password.get_secret_value()),
        role=UserRole.ADMIN,
    )
    db.add(user)
    await db.commit()
    return user
