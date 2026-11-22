"""Bir nechta sxema va endpointlarda ishlatiladigan umumiy turlar."""

from typing import Annotated, Any, ClassVar

from annotated_types import Interval
from pydantic import AfterValidator, BaseModel, ValidationInfo, field_validator

# PostgreSQL INTEGER chegaralari: bundan katta son bazada xato (500) beradi.
INT32_MIN = -(2**31)
INT32_MAX = 2**31 - 1


def _reject_nul(value: str) -> str:
    # PostgreSQL matnda NUL baytini saqlay olmaydi: tekshirilmasa 500 bo'ladi.
    if "\x00" in value:
        raise ValueError("Matnda NUL (\\u0000) belgisi bo'lmasligi kerak")
    return value


# Bazaga yoziladigan yoki so'rovda ishlatiladigan har bir matn shu tekshiruvdan o'tadi.
NoNul = AfterValidator(_reject_nul)
Text = Annotated[str, NoNul]

Id = Annotated[int, Interval(ge=1, le=INT32_MAX)]
Int32 = Annotated[int, Interval(ge=INT32_MIN, le=INT32_MAX)]


class PatchModel(BaseModel):
    """PATCH body: yuborilmagan maydon o'zgarmaydi.

    `nullable` ro'yxatida bo'lmagan maydonga `null` yuborilsa 422 qaytadi
    (jimgina e'tiborsiz qoldirilmaydi).
    """

    nullable: ClassVar[frozenset[str]] = frozenset()

    @field_validator("*")
    @classmethod
    def _reject_null(cls, value: Any, info: ValidationInfo) -> Any:
        if value is None and info.field_name not in cls.nullable:
            raise ValueError("Bu maydon null bo'lishi mumkin emas")
        return value
