"""So'rov hajmi chegarasi: oddiy so'rovlar kichik, katta body faqat rasm yuklashga."""

from datetime import UTC, datetime, timedelta

import pytest

from app.core.config import get_settings
from app.core.signature import NONCE_HEADER, SIGNATURE_HEADER, TIMESTAMP_HEADER
from tests.helpers import register, signed_request
from tests.test_auth_edge_cases import make_access_token, session_id_of

API = get_settings().api_prefix
UPLOAD_PATH = f"{API}/admin/menu/1/image"


def request_limit() -> int:
    return get_settings().max_request_kb * 1024


def too_big() -> bytes:
    return b"0" * (request_limit() + 1)


async def test_large_login_rejected_before_parsing(client):
    response = await client.post(
        f"{API}/auth/login", content=too_big(), headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "REQUEST_TOO_LARGE"


async def test_large_upload_without_token_rejected_before_auth(client):
    response = await client.put(UPLOAD_PATH, files={"image": ("x.png", too_big())})
    assert response.status_code == 413


async def test_limit_applies_without_content_length(client):
    async def chunks():
        for _ in range(3):
            yield b"x" * request_limit()

    # Generator body chunked yuboriladi, Content-Length bo'lmaydi.
    response = await client.post(f"{API}/auth/login", content=chunks())
    assert response.status_code == 413


async def test_small_request_passes(client):
    response = await client.post(
        f"{API}/auth/login", json={"email": "yoq@example.com", "password": "secret-pass"}
    )
    assert response.status_code == 401  # limitdan o'tdi, oddiy auth xatosi


async def test_fake_signature_header_does_not_raise_limit(client):
    headers = {SIGNATURE_HEADER: "x", TIMESTAMP_HEADER: "1", NONCE_HEADER: "n"}
    response = await client.put(UPLOAD_PATH, files={"image": ("x.png", too_big())}, headers=headers)
    assert response.status_code == 413


@pytest.mark.parametrize("kind", ["garbage", "expired"])
async def test_upload_with_invalid_token_is_401_not_413(client, kind):
    tokens = await register(client)
    token = "not-a-jwt"
    if kind == "expired":
        token = make_access_token(
            tokens["user"]["id"],
            session_id_of(tokens),
            exp=datetime.now(UTC) - timedelta(seconds=1),
        )
    response = await client.put(
        UPLOAD_PATH,
        files={"image": ("x.png", too_big())},
        headers={"Authorization": f"Bearer {token}"},
    )
    # Mijoz "fayl katta" emas, "token eskirgan" deb tushunib, refresh qiladi.
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_TOKEN"
    assert response.headers["WWW-Authenticate"] == "Bearer"


async def test_valid_token_gets_large_limit_on_upload_route(client):
    tokens = await register(client)
    response = await client.put(
        UPLOAD_PATH,
        files={"image": ("x.png", too_big())},
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    # Limitdan o'tdi: keyingi tekshiruv (imzo) rad etadi.
    assert response.json()["error"]["code"] == "SIGNATURE_MISSING"


async def test_valid_token_does_not_raise_limit_on_other_routes(client):
    tokens = await register(client)
    big_json = {"name": "x" * (request_limit() + 1)}
    response = await signed_request(client, tokens, "POST", "/admin/categories", big_json)
    assert response.status_code == 413


async def test_revoked_token_does_not_raise_limit_on_login(client):
    tokens = await register(client)
    await signed_request(client, tokens, "POST", "/auth/logout")
    response = await client.post(
        f"{API}/auth/login",
        content=b"x" * (5 * 1024 * 1024),
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert response.status_code == 413
