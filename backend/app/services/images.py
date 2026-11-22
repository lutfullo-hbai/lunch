"""Rasmlarni tekshirish, WebP'ga o'girish va diskka saqlash.

Har bir rasm uchun ikki fayl saqlanadi:
    menu/2026/11/<uuid>.webp        katta (IMAGE_SIZE)
    menu/2026/11/<uuid>_thumb.webp  kichik (IMAGE_THUMB_SIZE)
Bazada faqat katta faylning nisbiy yo'li saqlanadi.
"""

import io
import uuid
from datetime import UTC, datetime
from pathlib import Path

from fastapi import UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.core.errors import image_too_large, invalid_image
from app.core.media import OUTPUT_EXTENSION, thumb_path

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}


async def _read_limited(upload: UploadFile) -> bytes:
    max_bytes = get_settings().image_max_upload_mb * 1024 * 1024
    data = await upload.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise image_too_large(get_settings().image_max_upload_mb)
    if not data:
        raise invalid_image("Fayl bo'sh")
    return data


def _resize_to_webp(image: Image.Image, max_side: int, quality: int) -> bytes:
    copy = image.copy()
    copy.thumbnail((max_side, max_side))
    buffer = io.BytesIO()
    copy.save(buffer, format="WEBP", quality=quality)
    return buffer.getvalue()


def _process(data: bytes) -> tuple[bytes, bytes]:
    """Rasmni tekshiradi va (katta, kichik) WebP baytlarini qaytaradi."""
    settings = get_settings()
    # Pillow o'zi faqat 2 x MAX_IMAGE_PIXELS da xato beradi, shuning uchun o'lchamni
    # pikselga ochishdan oldin (faqat sarlavhadan) o'zimiz aniq tekshiramiz.
    Image.MAX_IMAGE_PIXELS = settings.image_max_pixels
    try:
        with Image.open(io.BytesIO(data)) as probe:
            if probe.format not in ALLOWED_FORMATS:
                raise invalid_image("Faqat JPEG, PNG yoki WebP rasm qabul qilinadi")
            width, height = probe.size
            if width * height > settings.image_max_pixels:
                raise invalid_image("Rasm o'lchami (piksellar soni) juda katta")
            probe.verify()  # fayl buzilmaganini tekshiradi
        with Image.open(io.BytesIO(data)) as source:
            image = ImageOps.exif_transpose(source)
            if image.mode not in ("RGB", "RGBA"):
                image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
            return (
                _resize_to_webp(image, settings.image_size, settings.image_quality),
                _resize_to_webp(image, settings.image_thumb_size, settings.image_quality),
            )
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, SyntaxError) as exc:
        raise invalid_image("Fayl rasm emas yoki buzilgan") from exc


def _write(relative_path: str, content: bytes) -> None:
    target = get_settings().media_dir / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)


async def save_menu_image(upload: UploadFile) -> str:
    """Rasmni saqlaydi va bazaga yoziladigan nisbiy yo'lni qaytaradi."""
    data = await _read_limited(upload)
    large, thumb = await run_in_threadpool(_process, data)

    now = datetime.now(UTC)
    relative = f"menu/{now:%Y}/{now:%m}/{uuid.uuid4().hex}{OUTPUT_EXTENSION}"
    await run_in_threadpool(_write, relative, large)
    await run_in_threadpool(_write, thumb_path(relative), thumb)
    return relative


def delete_image(relative_path: str | None) -> None:
    if not relative_path:
        return
    media_dir = get_settings().media_dir
    for path in (relative_path, thumb_path(relative_path)):
        Path(media_dir, path).unlink(missing_ok=True)
