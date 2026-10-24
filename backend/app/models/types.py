"""SQLAlchemy column helpers."""

from enum import Enum

from sqlalchemy import Enum as SAEnum


def enum_type(enum_cls: type[Enum], name: str, length: int = 32) -> SAEnum:
    """Return a portable, validated VARCHAR-backed enum column type."""
    return SAEnum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
        length=length,
    )
