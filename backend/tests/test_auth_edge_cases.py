"""Token va sessiya chekka holatlari: muddati o'tgan, mos kelmaydigan, bloklangan user."""

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from sqlalchemy import update

from app.core.config import get_settings
from app.models import RefreshToken, User
from tests.helpers import register, signed_request

API = get_settings().api_prefix


def make_access_token(user_id: int, session_id: str, **overrides) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "sid": session_id,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=5),
        **overrides,
    }
    return jwt.encode(payload, settings.jwt_secret.get_secret_value(), settings.jwt_algorithm)


def session_id_of(tokens: dict) -> str:
    return jwt.decode(tokens["access_token"], options={"verify_signature": False})["sid"]


async def test_expired_access_token(client):
    tokens = await register(client)
    expired = make_access_token(
        tokens["user"]["id"],
        session_id_of(tokens),
        exp=datetime.now(UTC) - timedelta(seconds=1),
    )
    response = await signed_request(client, {**tokens, "access_token": expired}, "GET", "/me")
    assert response.json()["error"]["code"] == "INVALID_TOKEN"


@pytest.mark.parametrize("overrides", [{"type": "refresh"}, {"sid": "not-a-uuid"}])
async def test_malformed_access_token(client, overrides):
    tokens = await register(client)
    token = make_access_token(tokens["user"]["id"], session_id_of(tokens), **overrides)
    response = await signed_request(client, {**tokens, "access_token": token}, "GET", "/me")
    assert response.json()["error"]["code"] == "INVALID_TOKEN"


async def test_access_token_with_another_users_session(client):
    ali = await register(client, email="ali@example.com")
    vali = await register(client, email="vali@example.com")
    # Alining ID'si, lekin Valining sessiyasi: sessiya Aliga tegishli emas.
    forged = make_access_token(ali["user"]["id"], session_id_of(vali))
    response = await signed_request(client, {**vali, "access_token": forged}, "GET", "/me")
    assert response.json()["error"]["code"] == "SESSION_REVOKED"


async def test_expired_session_rejects_access_and_refresh(client, db):
    tokens = await register(client)
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == tokens["user"]["id"])
        .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
    )

    me = await signed_request(client, tokens, "GET", "/me")
    assert me.json()["error"]["code"] == "SESSION_REVOKED"
    refresh = await client.post(
        f"{API}/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert refresh.json()["error"]["code"] == "INVALID_REFRESH_TOKEN"


async def test_inactive_user_cannot_refresh_or_use_api(client, db):
    tokens = await register(client)
    await db.execute(update(User).where(User.id == tokens["user"]["id"]).values(is_active=False))

    refresh = await client.post(
        f"{API}/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert refresh.status_code == 403
    assert refresh.json()["error"]["code"] == "USER_INACTIVE"
    me = await signed_request(client, tokens, "GET", "/me")
    assert me.json()["error"]["code"] == "USER_INACTIVE"


async def test_unknown_refresh_token(client):
    response = await client.post(f"{API}/auth/refresh", json={"refresh_token": "nope"})
    assert response.json()["error"]["code"] == "INVALID_REFRESH_TOKEN"
