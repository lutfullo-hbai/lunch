"""Testlar uchun yordamchilar: imzolangan so'rov yuborish."""

import json
import secrets
import time

from httpx import AsyncClient, Response

from app.core.config import get_settings
from app.core.signature import (
    NONCE_HEADER,
    SIGNATURE_HEADER,
    TIMESTAMP_HEADER,
    build_string_to_sign,
    compute_signature,
)


def signed_headers(
    tokens: dict, method: str, path: str, body: bytes = b"", timestamp: int | None = None
) -> dict[str, str]:
    ts = str(timestamp if timestamp is not None else int(time.time()))
    nonce = secrets.token_hex(16)
    string_to_sign = build_string_to_sign(method, path, ts, nonce, body)
    return {
        "Authorization": f"Bearer {tokens['access_token']}",
        TIMESTAMP_HEADER: ts,
        NONCE_HEADER: nonce,
        SIGNATURE_HEADER: compute_signature(tokens["signing_key"], string_to_sign),
    }


async def signed_request(
    client: AsyncClient, tokens: dict, method: str, path: str, payload: dict | None = None
) -> Response:
    full_path = get_settings().api_prefix + path
    body = json.dumps(payload).encode() if payload is not None else b""
    headers = signed_headers(tokens, method, full_path, body)
    if payload is not None:
        headers["Content-Type"] = "application/json"
    return await client.request(method, full_path, content=body, headers=headers)


async def register(
    client: AsyncClient, email: str = "ali@example.com", password: str = "secret-pass"
) -> dict:
    response = await client.post(
        get_settings().api_prefix + "/auth/register",
        json={"full_name": "Ali Valiyev", "email": email, "password": password},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def admin_tokens(client: AsyncClient, db) -> dict:
    """Admin rolidagi user yaratib, uning tokenlarini qaytaradi."""
    from app.models import User
    from app.models.enums import UserRole

    tokens = await register(client, email="admin@example.com")
    user = await db.get(User, tokens["user"]["id"])
    user.role = UserRole.ADMIN
    await db.commit()
    return tokens
