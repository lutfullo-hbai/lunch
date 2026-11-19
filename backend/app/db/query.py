"""Querylar uchun kichik yordamchilar."""

from sqlalchemy import ColumnElement
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
