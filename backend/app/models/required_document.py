"""Required-document rules per application type."""

from __future__ import annotations

from sqlalchemy import Boolean, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import ApplicationType
from app.models.types import enum_type


class RequiredDocument(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A document that an application type requires or accepts.

    The rows are configuration data, not application-specific uploads. They can
    be edited without changing the checklist logic.
    """

    __tablename__ = "required_documents"
    __table_args__ = (
        UniqueConstraint(
            "application_type",
            "doc_type",
            name="uq_required_documents_application_type_doc_type",
        ),
    )

    application_type: Mapped[ApplicationType] = mapped_column(
        enum_type(ApplicationType, "application_type", length=16),
        nullable=False,
        index=True,
    )
    doc_type: Mapped[str] = mapped_column(String(100), nullable=False)
    mandatory: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
