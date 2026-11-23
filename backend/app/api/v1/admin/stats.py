from fastapi import APIRouter

from app.api.deps import DbSession
from app.schemas.stats import StatsOut, StatsPeriod
from app.services import stats as service

router = APIRouter(prefix="/stats", tags=["admin: stats"])


@router.get("")
async def get_stats(db: DbSession, period: StatsPeriod = StatsPeriod.TODAY) -> StatsOut:
    """Dashboard ko'rsatkichlari: bugun, 7 kun yoki 30 kun (`TIMEZONE` bo'yicha)."""
    return await service.collect(db, period)
