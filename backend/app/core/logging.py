import logging

from app.core.config import get_settings


def setup_logging() -> None:
    logging.basicConfig(
        level=get_settings().log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    # httpx har so'rov URL'ini INFO'da yozadi, Telegram URL'ida esa bot tokeni bor.
    logging.getLogger("httpx").setLevel(logging.WARNING)
