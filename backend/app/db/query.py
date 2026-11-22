"""Querylar uchun kichik yordamchilar."""

from dataclasses import dataclass

from sqlalchemy import ColumnElement, Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

_LIKE_ESCAPE = "\\"


def contains(column: InstrumentedAttribute[str | None], text: str) -> ColumnElement[bool]:
    """Katta-kichik harfsiz "ichida bor" qidiruvi. `%` va `_` oddiy belgi sifatida qidiriladi."""
    escaped = (
        text.strip()
        .replace(_LIKE_ESCAPE, _LIKE_ESCAPE * 2)
        .replace("%", f"{_LIKE_ESCAPE}%")
        .replace("_", f"{_LIKE_ESCAPE}_")
    )
    return column.ilike(f"%{escaped}%", escape=_LIKE_ESCAPE)


@dataclass(frozen=True)
class PageResult[T]:
    items: list[T]
    total: int


async def paginate[T](
    db: AsyncSession, query: Select[tuple[T]], offset: int, limit: int
) -> PageResult[T]:
    """Umumiy sonni hisoblaydi va so'ralgan sahifani qaytaradi. `query` tartiblangan bo'lsin."""
    total = await db.scalar(select(func.count()).select_from(query.order_by(None).subquery()))
    rows = await db.scalars(query.offset(offset).limit(limit))
    return PageResult(items=list(rows), total=total or 0)
