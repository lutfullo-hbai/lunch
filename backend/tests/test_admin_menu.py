import io
from decimal import Decimal

import pytest
from PIL import Image

from app.core.config import get_settings
from app.core.signature import NONCE_HEADER, SIGNATURE_HEADER, TIMESTAMP_HEADER
from tests.helpers import admin_tokens, register, signed_headers, signed_request

API = get_settings().api_prefix


@pytest.fixture(autouse=True)
def media_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "media_dir", tmp_path)
    return tmp_path


@pytest.fixture
async def admin(client, db) -> dict:
    return await admin_tokens(client, db)


@pytest.fixture
async def category(client, admin) -> dict:
    response = await signed_request(client, admin, "POST", "/admin/categories", {"name": "Osh"})
    return response.json()


async def create_item(client, admin, category, **overrides) -> dict:
    payload = {"category_id": category["id"], "name": "Palov", "price": "45000", **overrides}
    response = await signed_request(client, admin, "POST", "/admin/menu", payload)
    assert response.status_code == 201, response.text
    return response.json()


def png_bytes(size=(2000, 1000)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, "orange").save(buffer, format="PNG")
    return buffer.getvalue()


async def upload(client, tokens, item_id: int, content: bytes, filename="palov.png"):
    """Multipart so'rovni oldin yasab, keyin aynan o'sha baytlarni imzolaymiz."""
    path = f"{API}/admin/menu/{item_id}/image"
    request = client.build_request("PUT", path, files={"image": (filename, content)})
    body = request.read()
    headers = signed_headers(tokens, "PUT", path, body)
    for name in ("Authorization", TIMESTAMP_HEADER, NONCE_HEADER, SIGNATURE_HEADER):
        request.headers[name] = headers[name]
    return await client.send(request)


async def test_regular_user_forbidden(client):
    user = await register(client)
    response = await signed_request(client, user, "GET", "/admin/menu")
    assert response.status_code == 403


async def test_create_item(client, admin, category):
    item = await create_item(client, admin, category, portion="350 g")
    assert item["category_name"] == "Osh"
    assert Decimal(item["price"]) == Decimal("45000")
    assert item["image_url"] is None


async def test_create_with_unknown_category(client, admin):
    response = await signed_request(
        client, admin, "POST", "/admin/menu", {"category_id": 999999, "name": "X", "price": "1"}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "CATEGORY_NOT_FOUND"


async def test_price_must_be_positive(client, admin, category):
    response = await signed_request(
        client,
        admin,
        "POST",
        "/admin/menu",
        {"category_id": category["id"], "name": "X", "price": "0"},
    )
    assert response.status_code == 422


async def test_list_filters_and_pagination(client, admin, category):
    await create_item(client, admin, category, name="Palov")
    await create_item(client, admin, category, name="Lag'mon", is_available=False)
    await create_item(client, admin, category, name="Manti")

    page = (await signed_request(client, admin, "GET", "/admin/menu?size=2")).json()
    assert page["total"] == 3
    assert len(page["items"]) == 2

    search = (await signed_request(client, admin, "GET", "/admin/menu?search=pal")).json()
    assert [i["name"] for i in search["items"]] == ["Palov"]

    hidden = (await signed_request(client, admin, "GET", "/admin/menu?is_available=false")).json()
    assert [i["name"] for i in hidden["items"]] == ["Lag'mon"]


async def test_update_item(client, admin, category):
    item = await create_item(client, admin, category, description="Eski")
    response = await signed_request(
        client,
        admin,
        "PATCH",
        f"/admin/menu/{item['id']}",
        {"price": "50000", "description": None, "name": None},
    )
    body = response.json()
    assert Decimal(body["price"]) == Decimal("50000")
    assert body["description"] is None  # bo'sh qilish mumkin
    assert body["name"] == "Palov"  # majburiy maydon null bilan o'chmaydi


async def test_soft_delete(client, admin, category, db):
    from app.models import MenuItem

    item = await create_item(client, admin, category)
    response = await signed_request(client, admin, "DELETE", f"/admin/menu/{item['id']}")
    assert response.status_code == 204

    assert (
        await signed_request(client, admin, "GET", f"/admin/menu/{item['id']}")
    ).status_code == 404
    row = await db.get(MenuItem, item["id"])
    assert row is not None and row.deleted_at is not None  # bazada qoladi

    # Kategoriyada faol ovqat qolmadi, endi o'chirsa bo'ladi.
    deleted = await signed_request(client, admin, "DELETE", f"/admin/categories/{category['id']}")
    assert deleted.status_code == 204


async def test_upload_image_resizes_to_webp(client, admin, category, media_dir):
    item = await create_item(client, admin, category)
    response = await upload(client, admin, item["id"], png_bytes())
    assert response.status_code == 200, response.text

    body = response.json()
    relative = body["image_url"].removeprefix(get_settings().media_url_prefix + "/")
    with Image.open(media_dir / relative) as large:
        assert large.format == "WEBP"
        assert max(large.size) == get_settings().image_size
    thumb = body["thumb_url"].removeprefix(get_settings().media_url_prefix + "/")
    with Image.open(media_dir / thumb) as small:
        assert max(small.size) == get_settings().image_thumb_size


async def test_replace_image_deletes_old_files(client, admin, category, media_dir):
    item = await create_item(client, admin, category)
    await upload(client, admin, item["id"], png_bytes())
    await upload(client, admin, item["id"], png_bytes())
    assert len(list(media_dir.rglob("*.webp"))) == 2  # faqat yangi rasm + thumb


async def test_delete_image(client, admin, category, media_dir):
    item = await create_item(client, admin, category)
    await upload(client, admin, item["id"], png_bytes())
    response = await signed_request(client, admin, "DELETE", f"/admin/menu/{item['id']}/image")
    assert response.json()["image_url"] is None
    assert list(media_dir.rglob("*.webp")) == []


async def test_upload_rejects_non_image(client, admin, category):
    item = await create_item(client, admin, category)
    response = await upload(client, admin, item["id"], b"not an image", filename="x.png")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_IMAGE"


async def test_upload_rejects_too_large(client, admin, category, monkeypatch):
    item = await create_item(client, admin, category)
    monkeypatch.setattr(get_settings(), "image_max_upload_mb", 1)
    response = await upload(client, admin, item["id"], b"0" * (1024 * 1024 + 1))
    assert response.status_code == 413


async def test_request_body_limit(client, db, admin, category, monkeypatch):
    item = await create_item(client, admin, category)
    # Middleware ilova yaratilganda sozlanadi, shuning uchun alohida ilova bilan tekshiramiz.
    from httpx import ASGITransport, AsyncClient

    from app.db.session import get_db
    from app.main import create_app

    monkeypatch.setattr(get_settings(), "max_request_mb", 1)
    small_app = create_app()
    small_app.dependency_overrides[get_db] = lambda: db
    async with AsyncClient(transport=ASGITransport(app=small_app), base_url="http://test") as c:
        response = await upload(c, admin, item["id"], b"0" * (2 * 1024 * 1024))
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "REQUEST_TOO_LARGE"


async def test_media_served_as_webp(media_dir):
    from httpx import ASGITransport, AsyncClient

    from app.main import create_app

    (media_dir / "menu").mkdir()
    Image.new("RGB", (10, 10)).save(media_dir / "menu" / "x.webp", format="WEBP")
    app = create_app()  # media papkasi ilova yaratilganda ulanadi
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        response = await c.get(f"{get_settings().media_url_prefix}/menu/x.webp")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/webp"


@pytest.mark.filterwarnings("ignore::PIL.Image.DecompressionBombWarning")
async def test_upload_rejects_too_many_pixels(client, admin, category, monkeypatch):
    item = await create_item(client, admin, category)
    # 40x40 = 1600 px: chegaradan oshadi, lekin Pillow'ning o'z 2x chegarasidan oshmaydi.
    monkeypatch.setattr(get_settings(), "image_max_pixels", 1000)
    response = await upload(client, admin, item["id"], png_bytes(size=(40, 40)))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_IMAGE"


async def test_upload_to_missing_item_writes_nothing(client, admin, media_dir):
    response = await upload(client, admin, 999999, png_bytes())
    assert response.status_code == 404
    assert list(media_dir.rglob("*.webp")) == []


async def test_search_treats_wildcards_literally(client, admin, category):
    await create_item(client, admin, category, name="Palov")
    await create_item(client, admin, category, name="100% mol go'shti")

    percent = (await signed_request(client, admin, "GET", "/admin/menu?search=%25")).json()
    underscore = (await signed_request(client, admin, "GET", "/admin/menu?search=_")).json()
    assert [i["name"] for i in percent["items"]] == ["100% mol go'shti"]
    assert underscore["total"] == 0


async def test_page_number_limit(client, admin):
    too_far = get_settings().page_number_max + 1
    response = await signed_request(client, admin, "GET", f"/admin/menu?page={too_far}")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "PAGE_OUT_OF_RANGE"
