"""Parol hashlash, JWT access token va refresh token yordamchilari."""

import hashlib
import hmac
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from app.core.config import BCRYPT_MAX_BYTES, get_settings


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt(rounds=get_settings().bcrypt_rounds)
    return bcrypt.hashpw(password.encode(), salt).decode()


def verify_password(password: str, password_hash: str) -> bool:
    encoded = password.encode()
    if len(encoded) > BCRYPT_MAX_BYTES:
        return False  # bunday parol hech qachon saqlanmagan, bcrypt esa xato beradi
    return bcrypt.checkpw(encoded, password_hash.encode())


def hash_token(token: str) -> str:
    """Refresh token bazada faqat SHA-256 hash ko'rinishida saqlanadi."""
    return hashlib.sha256(token.encode()).hexdigest()


def new_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def derive_signing_key(session_id: uuid.UUID) -> str:
    """Sessiyaga xos imzo kaliti. Bazada saqlanmaydi, har safar qayta hisoblanadi."""
    secret = get_settings().signing_secret.get_secret_value().encode()
    return hmac.new(secret, b"signing-key:" + session_id.bytes, hashlib.sha256).hexdigest()


@dataclass(frozen=True)
class AccessTokenClaims:
    user_id: int
    session_id: uuid.UUID


def create_access_token(user_id: int, session_id: uuid.UUID) -> tuple[str, int]:
    """Token va uning amal qilish muddatini (soniyada) qaytaradi."""
    settings = get_settings()
    ttl = timedelta(minutes=settings.access_token_ttl_minutes)
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "sid": str(session_id),
        "type": "access",
        "iat": now,
        "exp": now + ttl,
    }
    token = jwt.encode(
        payload, settings.jwt_secret.get_secret_value(), algorithm=settings.jwt_algorithm
    )
    return token, int(ttl.total_seconds())


def decode_access_token(token: str) -> AccessTokenClaims | None:
    """Token yaroqsiz yoki muddati o'tgan bo'lsa None qaytaradi."""
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "sid", "exp", "type"]},
        )
        if payload["type"] != "access":
            return None
        return AccessTokenClaims(user_id=int(payload["sub"]), session_id=uuid.UUID(payload["sid"]))
    except (jwt.PyJWTError, ValueError):
        return None
