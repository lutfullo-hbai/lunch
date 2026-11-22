"""Media fayllar yo'li va URL'i. Servis ham, javob sxemalari ham shundan foydalanadi."""

from pathlib import PurePosixPath

from app.core.config import get_settings

OUTPUT_EXTENSION = ".webp"
THUMB_SUFFIX = "_thumb"


def thumb_path(image_path: str) -> str:
    path = PurePosixPath(image_path)
    return str(path.with_name(f"{path.stem}{THUMB_SUFFIX}{path.suffix}"))


def public_url(relative_path: str | None) -> str | None:
    if relative_path is None:
        return None
    return f"{get_settings().media_url_prefix.rstrip('/')}/{relative_path}"
