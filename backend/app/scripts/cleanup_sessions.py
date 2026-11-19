"""Eski refresh token sessiyalarini bazadan o'chiradi.

Konteyner ishga tushganda bajariladi. Uzoq ishlaydigan serverda kuniga bir marta
cron orqali ham ishga tushirish mumkin: python -m app.scripts.cleanup_sessions
"""

import asyncio
import logging

from app.core.logging import setup_logging
from app.db.session import SessionFactory, engine
from app.services.auth import delete_stale_sessions

logger = logging.getLogger(__name__)


async def main() -> None:
    async with SessionFactory() as db:
        deleted = await delete_stale_sessions(db)
    await engine.dispose()
    logger.info("Eski sessiyalar o'chirildi: %s ta", deleted)


if __name__ == "__main__":
    setup_logging()
    asyncio.run(main())
