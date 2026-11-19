"""`.env` dagi SUPER_ADMIN_* asosida super adminni yaratadi. Qayta ishga tushirish xavfsiz.

Ishlatish: python -m app.scripts.create_super_admin
"""

import asyncio
import logging

from app.core.logging import setup_logging
from app.db.session import SessionFactory, engine
from app.services.auth import SuperAdminEmailTakenError, ensure_super_admin

logger = logging.getLogger(__name__)


async def main() -> None:
    try:
        async with SessionFactory() as db:
            user = await ensure_super_admin(db)
    except SuperAdminEmailTakenError as exc:
        # API ishlashda davom etadi: aks holda emailni bilgan odam register qilib,
        # konteynerni ishga tushmaydigan qilib qo'yishi mumkin edi.
        logger.error(
            "SUPER_ADMIN_EMAIL (%s) oddiy userga tegishli, admin qilinmadi. "
            "Boshqa email tanlang yoki o'sha userni tekshirib, qo'lda hal qiling",
            exc,
        )
        return
    finally:
        await engine.dispose()
    if user is None:
        logger.warning("SUPER_ADMIN_EMAIL yoki SUPER_ADMIN_PASSWORD berilmagan, o'tkazib yuborildi")
    else:
        logger.info("Super admin tayyor: %s", user.email)


if __name__ == "__main__":
    setup_logging()
    asyncio.run(main())
