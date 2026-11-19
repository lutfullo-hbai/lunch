import hmac
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.body_buffer import RAW_BODY_STATE_KEY
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import decode_access_token, derive_signing_key
from app.core.signature import (
    NONCE_HEADER,
    SIGNATURE_HEADER,
    TIMESTAMP_HEADER,
    NonceStore,
    build_string_to_sign,
    compute_signature,
    is_timestamp_fresh,
)
from app.db.session import get_db
from app.models import RefreshToken, User
from app.models.enums import UserRole

DbSession = Annotated[AsyncSession, Depends(get_db)]

_bearer = HTTPBearer(auto_error=False)


def get_nonce_store(request: Request) -> NonceStore:
    return request.app.state.nonce_store


@dataclass(frozen=True)
class AuthContext:
    user: User
    session: RefreshToken


def _unauthorized(code: str, message: str) -> AppError:
    return AppError(
        status.HTTP_401_UNAUTHORIZED, code, message, headers={"WWW-Authenticate": "Bearer"}
    )


async def _verify_signature(request: Request, signing_key: str, nonces: NonceStore) -> None:
    timestamp = request.headers.get(TIMESTAMP_HEADER)
    nonce = request.headers.get(NONCE_HEADER)
    signature = request.headers.get(SIGNATURE_HEADER)
    if not (timestamp and nonce and signature):
        raise _unauthorized("SIGNATURE_MISSING", "So'rov imzosi yo'q")

    if not is_timestamp_fresh(timestamp, get_settings().signature_max_skew_seconds):
        raise _unauthorized("SIGNATURE_EXPIRED", "So'rov vaqti eskirgan")

    path = request.url.path
    if request.url.query:
        path = f"{path}?{request.url.query}"
    expected = compute_signature(
        signing_key,
        build_string_to_sign(
            request.method, path, timestamp, nonce, getattr(request.state, RAW_BODY_STATE_KEY, b"")
        ),
    )
    if not hmac.compare_digest(expected, signature):
        raise _unauthorized("SIGNATURE_INVALID", "So'rov imzosi noto'g'ri")

    if not nonces.use(nonce):
        raise _unauthorized("SIGNATURE_REPLAYED", "Bu so'rov allaqachon yuborilgan")


async def get_auth_context(
    request: Request,
    db: DbSession,
    nonces: Annotated[NonceStore, Depends(get_nonce_store)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> AuthContext:
    """Access token, sessiya va so'rov imzosini tekshiradi."""
    if credentials is None:
        raise _unauthorized("NOT_AUTHENTICATED", "Tizimga kiring")

    claims = decode_access_token(credentials.credentials)
    if claims is None:
        raise _unauthorized("INVALID_TOKEN", "Access token yaroqsiz yoki muddati o'tgan")

    session = await db.scalar(
        select(RefreshToken).where(
            RefreshToken.jti == claims.session_id,
            RefreshToken.user_id == claims.user_id,
            RefreshToken.revoked_at.is_(None),
            RefreshToken.expires_at > datetime.now(UTC),
        )
    )
    if session is None:
        raise _unauthorized("SESSION_REVOKED", "Sessiya tugagan, qayta kiring")

    await _verify_signature(request, derive_signing_key(session.jti), nonces)

    user = await db.get(User, claims.user_id)
    if user is None or not user.is_active:
        raise AppError(status.HTTP_403_FORBIDDEN, "USER_INACTIVE", "Hisob bloklangan")
    return AuthContext(user=user, session=session)


Auth = Annotated[AuthContext, Depends(get_auth_context)]


async def get_current_user(auth: Auth) -> User:
    return auth.user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def require_admin(user: CurrentUser) -> User:
    if user.role is not UserRole.ADMIN:
        raise AppError(status.HTTP_403_FORBIDDEN, "FORBIDDEN", "Bu amal faqat admin uchun")
    return user


AdminUser = Annotated[User, Depends(require_admin)]
