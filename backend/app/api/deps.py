import hmac
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.body_buffer import RAW_BODY_STATE_KEY
from app.core.config import get_settings
from app.core.errors import forbidden, too_many_requests, unauthorized, user_inactive
from app.core.rate_limit import RateLimiter
from app.core.security import decode_access_token, derive_signing_key
from app.core.signature import (
    NONCE_HEADER,
    SIGNATURE_HEADER,
    TIMESTAMP_HEADER,
    NonceStore,
    build_string_to_sign,
    canonical_path,
    compute_signature,
    is_timestamp_fresh,
)
from app.db.session import SessionMaker, get_db, get_session_maker
from app.models import RefreshToken, User
from app.models.enums import UserRole

DbSession = Annotated[AsyncSession, Depends(get_db)]
Sessions = Annotated[SessionMaker, Depends(get_session_maker)]

_bearer = HTTPBearer(auto_error=False)


def get_nonce_store(request: Request) -> NonceStore:
    return request.app.state.nonce_store


def rate_limit(action: str):
    """IP bo'yicha rate limit dependency. Chegara `.env` dagi `<ACTION>_RATE_LIMIT` va
    `<ACTION>_RATE_WINDOW_SECONDS` dan olinadi."""

    async def check(request: Request) -> None:
        settings = get_settings()
        limiter: RateLimiter = request.app.state.rate_limiter
        client_ip = request.client.host if request.client else "unknown"
        retry_after = limiter.hit(
            f"{action}:{client_ip}",
            limit=getattr(settings, f"{action}_rate_limit"),
            window_seconds=getattr(settings, f"{action}_rate_window_seconds"),
        )
        if retry_after is not None:
            raise too_many_requests(retry_after)

    return Depends(check)


@dataclass(frozen=True)
class AuthContext:
    user: User
    session: RefreshToken


async def _verify_signature(request: Request, signing_key: str, nonces: NonceStore) -> None:
    timestamp = request.headers.get(TIMESTAMP_HEADER)
    nonce = request.headers.get(NONCE_HEADER)
    signature = request.headers.get(SIGNATURE_HEADER)
    if not (timestamp and nonce and signature):
        raise unauthorized("SIGNATURE_MISSING", "So'rov imzosi yo'q")
    if len(nonce) > get_settings().nonce_max_length:
        raise unauthorized("SIGNATURE_INVALID", "Nonce juda uzun")

    if not is_timestamp_fresh(timestamp, get_settings().signature_max_skew_seconds):
        raise unauthorized("SIGNATURE_EXPIRED", "So'rov vaqti eskirgan")

    # Dekodlangan path emas, mijoz yuborgan xom baytlar: %2F, %0A kabi belgilar
    # imzo matnini o'zgartira olmaydi.
    raw_path = request.scope.get("raw_path") or request.scope["path"].encode()
    path = canonical_path(raw_path, request.scope.get("query_string", b""))
    expected = compute_signature(
        signing_key,
        build_string_to_sign(
            request.method, path, timestamp, nonce, getattr(request.state, RAW_BODY_STATE_KEY, b"")
        ),
    )
    if not hmac.compare_digest(expected, signature):
        raise unauthorized("SIGNATURE_INVALID", "So'rov imzosi noto'g'ri")

    if not nonces.use(nonce):
        raise unauthorized("SIGNATURE_REPLAYED", "Bu so'rov allaqachon yuborilgan")


async def get_auth_context(
    request: Request,
    db: DbSession,
    nonces: Annotated[NonceStore, Depends(get_nonce_store)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> AuthContext:
    """Access token, sessiya va so'rov imzosini tekshiradi."""
    if credentials is None:
        raise unauthorized("NOT_AUTHENTICATED", "Tizimga kiring")

    claims = decode_access_token(credentials.credentials)
    if claims is None:
        raise unauthorized("INVALID_TOKEN", "Access token yaroqsiz yoki muddati o'tgan")

    session = await db.scalar(
        select(RefreshToken).where(
            RefreshToken.jti == claims.session_id,
            RefreshToken.user_id == claims.user_id,
            RefreshToken.revoked_at.is_(None),
            RefreshToken.expires_at > datetime.now(UTC),
        )
    )
    if session is None:
        raise unauthorized("SESSION_REVOKED", "Sessiya tugagan, qayta kiring")

    await _verify_signature(request, derive_signing_key(session.jti), nonces)

    user = await db.get(User, claims.user_id)
    if user is None or not user.is_active:
        raise user_inactive()
    return AuthContext(user=user, session=session)


Auth = Annotated[AuthContext, Depends(get_auth_context)]


async def get_current_user(auth: Auth) -> User:
    return auth.user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def require_admin(user: CurrentUser) -> User:
    if user.role is not UserRole.ADMIN:
        raise forbidden()
    return user


AdminUser = Annotated[User, Depends(require_admin)]
