"""Oddiy user hech bir admin endpointiga, ayniqsa yozish amallariga kira olmaydi."""

import re

import pytest

from app.core.config import get_settings
from tests.helpers import register, signed_request

ADMIN_ENDPOINTS = [
    ("GET", "/admin/categories", None),
    ("POST", "/admin/categories", {"name": "Osh"}),
    ("PATCH", "/admin/categories/1", {"name": "Osh"}),
    ("DELETE", "/admin/categories/1", None),
    ("GET", "/admin/menu", None),
    ("GET", "/admin/menu/1", None),
    ("POST", "/admin/menu", {"category_id": 1, "name": "Osh", "price": "1"}),
    ("PATCH", "/admin/menu/1", {"name": "Osh"}),
    ("DELETE", "/admin/menu/1", None),
    ("DELETE", "/admin/menu/1/image", None),
    ("GET", "/admin/users", None),
    ("GET", "/admin/users/1", None),
    ("GET", "/admin/users/1/orders", None),
    ("PATCH", "/admin/users/1/status", {"is_active": False}),
    ("GET", "/admin/orders", None),
    ("GET", "/admin/orders/1", None),
    ("PATCH", "/admin/orders/1/status", {"status": "accepted"}),
    ("POST", "/admin/orders/1/notify", None),
]


@pytest.mark.parametrize(("method", "path", "payload"), ADMIN_ENDPOINTS)
async def test_regular_user_gets_403(client, method, path, payload):
    user = await register(client)
    response = await signed_request(client, user, method, path, payload)
    assert response.status_code == 403, response.text
    assert response.json()["error"]["code"] == "FORBIDDEN"


async def test_regular_user_cannot_upload_image(client):
    from tests.test_admin_menu import png_bytes, upload

    user = await register(client)
    response = await upload(client, user, 1, png_bytes())
    assert response.status_code == 403


def test_every_admin_route_is_covered(app):
    """Yangi admin endpointi qo'shilsa, u ham shu ro'yxatga kirishi kerak."""
    prefix = get_settings().api_prefix
    routes = {
        (method.upper(), re.sub(r"\{[^}]+\}", "1", path.removeprefix(prefix)))
        for path, operations in app.openapi()["paths"].items()
        if path.startswith(f"{prefix}/admin")
        for method in operations
    }
    covered = {(m, p) for m, p, _ in ADMIN_ENDPOINTS} | {("PUT", "/admin/menu/1/image")}
    assert routes == covered
