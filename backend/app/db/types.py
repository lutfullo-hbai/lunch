from enum import StrEnum

from sqlalchemy import Enum


def pg_enum(enum_cls: type[StrEnum], name: str) -> Enum:
    """StrEnum'ni PostgreSQL ENUM'ga aylantiradi: bazada nomlar emas, qiymatlar saqlanadi."""
    return Enum(enum_cls, name=name, values_callable=lambda cls: [item.value for item in cls])
