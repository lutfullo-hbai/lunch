"""So'rov hajmi chegarasi: tokenli va tokensiz so'rovlar uchun."""

import pytest

from app.core.config import get_settings
from app.core.signature import NONCE_HEADER, SIGNATURE_HEADER, TIMESTAMP_HEADER
from tests.helpers import register

API = get_settings().api_prefix


def anonymous_limit() -> int:
    return get_settings().max_anonymous_request_kb * 1024


async def test_anonymous_large_login_rejected_before_parsing(client):
    big = b"x" * (anonymous_limit() + 1)
    response = await client.post(
        f"{API}/auth/login", content=big, headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "REQUEST_TOO_LARGE"


async def test_anonymous_large_upload_rejected_before_auth(client):
    # Tokensiz katta fayl: 401 gacha yetib bormasdan 413.
    big = b"0" * (anonymous_limit() + 1)
    response = await client.put(f"{API}/admin/menu/1/image", files={"image": ("x.png", big)})
    assert response.status_code == 413


async def test_limit_applies_without_content_length(client):
    async def chunks():
        for _ in range(3):
            yield b"x" * anonymous_limit()

    # Generator body chunked yuboriladi, Content-Length bo'lmaydi.
    response = await client.post(f"{API}/auth/login", content=chunks())
    assert response.status_code == 413


async def test_small_anonymous_request_passes(client):
    response = await client.post(
        f"{API}/auth/login", json={"email": "yoq@example.com", "password": "secret-pass"}
    )
    assert response.status_code == 401  # limitdan o'tdi, oddiy auth xatosi


@pytest.mark.parametrize(
    "headers",
    [
        {SIGNATURE_HEADER: "x", TIMESTAMP_HEADER: "1", NONCE_HEADER: "n"},
        {"Authorization": "Bearer not-a-jwt", SIGNATURE_HEADER: "x"},
    ],
)
async def test_fake_signature_header_does_not_raise_limit(client, headers):
    big = b"0" * (anonymous_limit() + 1)
    response = await client.put(
        f"{API}/admin/menu/1/image", files={"image": ("x.png", big)}, headers=headers
    )
    assert response.status_code == 413


async def test_valid_token_gets_large_limit(client):
    tokens = await register(client)
    big = b"0" * (anonymous_limit() + 1)
    response = await client.put(
        f"{API}/admin/menu/1/image",
        files={"image": ("x.png", big)},
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    # Limitdan o'tdi: keyingi tekshiruv (imzo) rad etadi.
    assert response.json()["error"]["code"] == "SIGNATURE_MISSING"
