import time

import pytest

from app.core.config import get_settings
from tests.helpers import register, signed_headers, signed_request

API = get_settings().api_prefix


async def test_register_returns_tokens(client):
    tokens = await register(client, email="Ali@Example.com")

    assert tokens["user"]["email"] == "ali@example.com"
    assert tokens["user"]["role"] == "user"
    assert tokens["expires_in"] == get_settings().access_token_ttl_minutes * 60
    assert tokens["signing_key"]


async def test_register_duplicate_email(client):
    await register(client)
    response = await client.post(
        f"{API}/auth/register",
        json={"full_name": "Boshqa", "email": "ali@example.com", "password": "secret-pass"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "EMAIL_TAKEN"


async def test_register_short_password(client):
    response = await client.post(
        f"{API}/auth/register",
        json={"full_name": "Ali", "email": "ali@example.com", "password": "123"},
    )
    assert response.status_code == 422


@pytest.mark.parametrize("full_name", ["     ", "  a  "])
async def test_register_blank_or_short_name_after_strip(client, full_name):
    response = await client.post(
        f"{API}/auth/register",
        json={"full_name": full_name, "email": "ali@example.com", "password": "secret-pass"},
    )
    assert response.status_code == 422


async def test_register_strips_name(client):
    response = await client.post(
        f"{API}/auth/register",
        json={
            "full_name": "  Ali Valiyev  ",
            "email": "ali@example.com",
            "password": "secret-pass",
        },
    )
    assert response.json()["user"]["full_name"] == "Ali Valiyev"


async def test_login_success_and_wrong_password(client):
    await register(client)

    ok = await client.post(
        f"{API}/auth/login", json={"email": "ali@example.com", "password": "secret-pass"}
    )
    assert ok.status_code == 200

    bad = await client.post(
        f"{API}/auth/login", json={"email": "ali@example.com", "password": "wrong-pass"}
    )
    assert bad.status_code == 401
    assert bad.json()["error"]["code"] == "INVALID_CREDENTIALS"


async def test_login_unknown_email(client):
    response = await client.post(
        f"{API}/auth/login", json={"email": "yoq@example.com", "password": "secret-pass"}
    )
    assert response.status_code == 401


async def test_me_with_signed_request(client):
    tokens = await register(client)
    response = await signed_request(client, tokens, "GET", "/me")

    assert response.status_code == 200
    assert response.json()["email"] == "ali@example.com"


async def test_me_without_signature(client):
    tokens = await register(client)
    response = await client.get(
        f"{API}/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "SIGNATURE_MISSING"


async def test_me_without_token(client):
    response = await client.get(f"{API}/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "NOT_AUTHENTICATED"


async def test_signature_wrong_key(client):
    tokens = await register(client)
    forged = {**tokens, "signing_key": "x" * 64}
    response = await signed_request(client, forged, "GET", "/me")
    assert response.json()["error"]["code"] == "SIGNATURE_INVALID"


async def test_signature_expired(client):
    tokens = await register(client)
    old = int(time.time()) - get_settings().signature_max_skew_seconds - 5
    headers = signed_headers(tokens, "GET", f"{API}/me", timestamp=old)
    response = await client.get(f"{API}/me", headers=headers)
    assert response.json()["error"]["code"] == "SIGNATURE_EXPIRED"


async def test_signature_replay_rejected(client):
    tokens = await register(client)
    headers = signed_headers(tokens, "GET", f"{API}/me")

    first = await client.get(f"{API}/me", headers=headers)
    second = await client.get(f"{API}/me", headers=headers)

    assert first.status_code == 200
    assert second.json()["error"]["code"] == "SIGNATURE_REPLAYED"


async def test_refresh_rotates_token(client):
    tokens = await register(client)
    response = await client.post(
        f"{API}/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert response.status_code == 200
    new_tokens = response.json()
    assert new_tokens["refresh_token"] != tokens["refresh_token"]

    # Eski sessiya bekor bo'ldi, yangisi ishlaydi.
    old_me = await signed_request(client, tokens, "GET", "/me")
    new_me = await signed_request(client, new_tokens, "GET", "/me")
    assert old_me.json()["error"]["code"] == "SESSION_REVOKED"
    assert new_me.status_code == 200


async def test_refresh_reuse_revokes_all_sessions(client, monkeypatch):
    # Grace oynasi tugagan: eski token qayta kelsa, bu o'g'irlik deb hisoblanadi.
    monkeypatch.setattr(get_settings(), "refresh_reuse_grace_seconds", 0)
    tokens = await register(client)
    rotated = (
        await client.post(f"{API}/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    ).json()

    reuse = await client.post(
        f"{API}/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert reuse.status_code == 401

    # O'g'irlangan token qayta ishlatildi, shuning uchun yangi sessiya ham yopildi.
    me = await signed_request(client, rotated, "GET", "/me")
    assert me.json()["error"]["code"] == "SESSION_REVOKED"


async def test_logout_revokes_session(client):
    tokens = await register(client)
    logout = await signed_request(client, tokens, "POST", "/auth/logout")
    assert logout.status_code == 204

    me = await signed_request(client, tokens, "GET", "/me")
    assert me.json()["error"]["code"] == "SESSION_REVOKED"

    refresh = await client.post(
        f"{API}/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert refresh.status_code == 401


async def test_refresh_after_logout_keeps_other_sessions(client, monkeypatch):
    # Bir tabda logout, boshqa tab eski token bilan refresh qiladi: bu o'g'irlik emas.
    monkeypatch.setattr(get_settings(), "refresh_reuse_grace_seconds", 0)
    tokens = await register(client)
    other = (
        await client.post(
            f"{API}/auth/login", json={"email": "ali@example.com", "password": "secret-pass"}
        )
    ).json()
    await signed_request(client, tokens, "POST", "/auth/logout")

    refresh = await client.post(
        f"{API}/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert refresh.json()["error"]["code"] == "INVALID_REFRESH_TOKEN"
    assert (await signed_request(client, other, "GET", "/me")).status_code == 200


async def test_reuse_within_grace_keeps_sessions(client):
    tokens = await register(client)
    rotated = (
        await client.post(f"{API}/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    ).json()

    again = await client.post(
        f"{API}/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert again.json()["error"]["code"] == "REFRESH_TOKEN_ROTATED"
    assert (await signed_request(client, rotated, "GET", "/me")).status_code == 200


@pytest.mark.parametrize("email", ["ali@example.com", "yoq@example.com"])
async def test_login_multibyte_long_password_is_422_not_500(client, email):
    await register(client)
    # 72 belgi, lekin 144 bayt: belgi bo'yicha tekshirilsa bcrypt 500 berardi.
    response = await client.post(f"{API}/auth/login", json={"email": email, "password": "ж" * 72})
    assert response.status_code == 422


def test_verify_password_rejects_over_limit_without_error():
    from app.core.config import BCRYPT_MAX_BYTES
    from app.core.security import hash_password, verify_password

    assert verify_password("a" * (BCRYPT_MAX_BYTES + 1), hash_password("secret-pass")) is False


def test_super_admin_password_over_limit_rejected():
    from pydantic import ValidationError

    from app.core.config import Settings

    with pytest.raises(ValidationError):
        Settings(super_admin_password="ж" * 40)


def test_signing_secret_must_differ_from_jwt_secret():
    from pydantic import ValidationError

    from app.core.config import Settings

    with pytest.raises(ValidationError, match="SIGNING_SECRET"):
        Settings(signing_secret=get_settings().jwt_secret.get_secret_value())


def test_signing_key_uses_signing_secret(monkeypatch):
    import uuid

    from pydantic import SecretStr

    from app.core.security import derive_signing_key

    session_id = uuid.uuid4()
    before = derive_signing_key(session_id)
    monkeypatch.setattr(get_settings(), "signing_secret", SecretStr("z" * 40))
    assert derive_signing_key(session_id) != before


async def test_signature_too_long_nonce(client):
    tokens = await register(client)
    headers = signed_headers(tokens, "GET", f"{API}/me")
    headers["X-Nonce"] = "n" * (get_settings().nonce_max_length + 1)
    response = await client.get(f"{API}/me", headers=headers)
    assert response.json()["error"]["code"] == "SIGNATURE_INVALID"


async def test_signature_covers_query_string(client):
    tokens = await register(client)
    headers = signed_headers(tokens, "GET", f"{API}/me?a=1")
    # Imzo `?a=1` uchun berilgan, query o'zgartirilsa rad etiladi.
    response = await client.get(f"{API}/me?a=2", headers=headers)
    assert response.json()["error"]["code"] == "SIGNATURE_INVALID"


async def test_signature_uses_raw_encoded_path(client):
    tokens = await register(client)
    # Mijoz %-kodlangan yo'l yuborsa, aynan shu baytlar imzolanadi.
    raw = f"{API}/m%65"  # server uchun bu /me
    headers = signed_headers(tokens, "GET", raw)
    response = await client.get(raw, headers=headers)
    assert response.status_code == 200, response.text


def test_nonce_store_expires_old_entries(monkeypatch):
    from app.core import signature

    clock = [1000.0]
    monkeypatch.setattr(signature.time, "monotonic", lambda: clock[0])
    store = signature.NonceStore(ttl_seconds=10)

    assert store.use("a") is True
    assert store.use("a") is False
    clock[0] += 11
    assert store.use("b") is True
    assert store.use("a") is True  # muddati o'tdi, xotiradan chiqarildi


async def test_delete_stale_sessions(db):
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import select

    from app.models import RefreshToken, User
    from app.services.auth import delete_stale_sessions

    user = User(email="eski@example.com", password_hash="x", full_name="Eski")
    db.add(user)
    await db.flush()
    now = datetime.now(UTC)
    old = now - timedelta(days=get_settings().token_retention_days + 1)
    db.add_all(
        [
            RefreshToken(user_id=user.id, token_hash="a" * 64, expires_at=old),
            RefreshToken(
                user_id=user.id,
                token_hash="b" * 64,
                expires_at=now + timedelta(days=1),
                revoked_at=old,
            ),
            RefreshToken(
                user_id=user.id,
                token_hash="c" * 64,
                expires_at=now + timedelta(days=1),
                revoked_at=now,
            ),
            RefreshToken(user_id=user.id, token_hash="d" * 64, expires_at=now + timedelta(days=1)),
        ]
    )
    await db.flush()

    assert await delete_stale_sessions(db) == 2
    left = await db.scalars(select(RefreshToken.token_hash).where(RefreshToken.user_id == user.id))
    assert sorted(h[0] for h in left) == ["c", "d"]  # yaqinda bekor qilingan va faol qoldi
