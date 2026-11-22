from typing import Annotated, Self

from fastapi import Depends, Query
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.errors import validation_error
from app.db.query import PageResult


class Page[T](BaseModel):
    items: list[T]
    total: int
    page: int
    size: int

    @classmethod
    def of(cls, result: PageResult, params: "PageParams") -> Self:
        """Servis natijasini javobga aylantiradi: ORM obyektlar `T` sxemasi bilan tekshiriladi."""
        return cls(items=result.items, total=result.total, page=params.page, size=params.size)


class PageParams(BaseModel):
    page: int
    size: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size


def _page_params(
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int | None, Query(ge=1)] = None,
) -> PageParams:
    settings = get_settings()
    if page > settings.page_number_max:
        raise validation_error("page", f"page {settings.page_number_max} dan oshmasligi kerak")
    size = min(size or settings.page_size_default, settings.page_size_max)
    return PageParams(page=page, size=size)


Pagination = Annotated[PageParams, Depends(_page_params)]
