"""Chegaradan tashqari kiritish 500 emas, 422 qaytarishi va jimgina o'tib ketmasligi."""

import pytest

from app.schemas.types import INT32_MAX
from tests.helpers import admin_tokens, signed_request

TOO_BIG = INT32_MAX + 1


@pytest.fixture
async def admin(client, db) -> dict:
    return await admin_tokens(client, db)


@pytest.fixture
async def category(client, admin) -> dict:
    response = await signed_request(client, admin, "POST", "/admin/categories", {"name": "Osh"})
    return response.json()


@pytest.fixture
async def item(client, admin, category) -> dict:
    response = await signed_request(
        client,
        admin,
        "POST",
        "/admin/menu",
        {"category_id": category["id"], "name": "Palov", "price": "45000"},
    )
    return response.json()


def assert_validation_error(response, field: str) -> None:
    assert response.status_code == 422, response.text
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert field in [d["field"] for d in error["details"]]


@pytest.mark.parametrize(
    ("method", "path", "field"),
    [
        ("GET", f"/admin/menu/{TOO_BIG}", "item_id"),
        ("DELETE", f"/admin/menu/{TOO_BIG}/image", "item_id"),
        ("PATCH", f"/admin/categories/{TOO_BIG}", "category_id"),
        ("GET", f"/admin/users/{TOO_BIG}", "user_id"),
        ("GET", f"/admin/orders/{TOO_BIG}", "order_id"),
        ("GET", "/admin/orders/0", "order_id"),
        ("GET", f"/admin/menu?category_id={TOO_BIG}", "category_id"),
        ("GET", f"/admin/orders?user_id={TOO_BIG}", "user_id"),
    ],
)
async def test_out_of_range_ids_are_422(client, admin, method, path, field):
    payload = {} if method == "PATCH" else None
    response = await signed_request(client, admin, method, path, payload)
    assert_validation_error(response, field)


async def test_body_ids_and_sort_order_are_bounded(client, admin):
    menu = await signed_request(
        client, admin, "POST", "/admin/menu", {"category_id": TOO_BIG, "name": "X", "price": "1"}
    )
    assert_validation_error(menu, "category_id")

    category = await signed_request(
        client, admin, "POST", "/admin/categories", {"name": "Osh", "sort_order": TOO_BIG}
    )
    assert_validation_error(category, "sort_order")


@pytest.mark.parametrize(
    "query",
    ["date_to=9999-12-31", "date_from=0001-01-01", "date_from=0001-01-01&date_to=0001-01-01"],
)
async def test_extreme_dates_are_not_500(client, admin, query):
    response = await signed_request(client, admin, "GET", f"/admin/orders?{query}")
    assert response.status_code == 200


@pytest.mark.parametrize("field", ["name", "price", "category_id", "is_available"])
async def test_menu_patch_null_on_required_field_is_422(client, admin, item, field):
    response = await signed_request(
        client, admin, "PATCH", f"/admin/menu/{item['id']}", {field: None}
    )
    assert_validation_error(response, field)


@pytest.mark.parametrize("field", ["name", "sort_order", "is_active"])
async def test_category_patch_null_is_422(client, admin, category, field):
    response = await signed_request(
        client, admin, "PATCH", f"/admin/categories/{category['id']}", {field: None}
    )
    assert_validation_error(response, field)


NUL = "a\u0000b"


async def test_register_with_nul_is_422(client):
    from app.core.config import get_settings

    response = await client.post(
        f"{get_settings().api_prefix}/auth/register",
        json={"full_name": NUL, "email": "nul@example.com", "password": "secret-pass"},
    )
    assert_validation_error(response, "full_name")


@pytest.mark.parametrize(
    ("method", "path", "payload", "field"),
    [
        ("GET", "/admin/users?search=%00", None, "search"),
        ("GET", "/admin/menu?search=%00", None, "search"),
        ("POST", "/admin/categories", {"name": NUL}, "name"),
    ],
)
async def test_admin_nul_is_422(client, admin, method, path, payload, field):
    response = await signed_request(client, admin, method, path, payload)
    assert_validation_error(response, field)


@pytest.mark.parametrize("field", ["name", "description", "portion"])
async def test_menu_text_with_nul_is_422(client, admin, item, field):
    response = await signed_request(
        client, admin, "PATCH", f"/admin/menu/{item['id']}", {field: NUL}
    )
    assert_validation_error(response, field)


async def test_login_email_with_nul_is_422(client):
    from app.core.config import get_settings

    response = await client.post(
        f"{get_settings().api_prefix}/auth/login",
        json={"email": "a\u0000@example.com", "password": "secret-pass"},
    )
    assert_validation_error(response, "email")
