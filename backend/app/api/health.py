import logging

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.deps import DbSession

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


@router.get("/health")
async def health(db: DbSession) -> JSONResponse:
    """Monitoring uchun: API va ma'lumotlar bazasi holati."""
    try:
        await db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        logger.exception("Health check: bazaga ulanib bo'lmadi")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "error", "database": "unavailable"},
        )
    return JSONResponse(content={"status": "ok", "database": "ok"})
