"""Required-document rules per application type."""

from __future__ import annotations

from sqlalchemy import Boolean, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class RequiredDocument(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A document that an application type requires or accepts.

    The rows are configuration data, not application-specific uploads. They can
    be edited without changing the checklist logic. ``condition_expr`` holds a
    small, documented expression such as ``land_ownership == 'LEASED'`` so a
    document can be conditional without a code change.
    """

    __tablename__ = "required_documents"
    __table_args__ = (
        UniqueConstraint(
            "application_type",
            "doc_type",
            name="uq_required_documents_application_type_doc_type",
        ),
    )

    application_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    doc_type: Mapped[str] = mapped_column(String(100), nullable=False)
    doc_code: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    """APH document code, for example AFFIDAVIT_2 or LAND_LEASE_DEED."""
    condition_expr: Mapped[str | None] = mapped_column(Text, nullable=True)
    apH_clause: Mapped[str] = mapped_column(String(64), nullable=False)
    """APH clause that requires the document, for example ``APH Annexure-1``."""
    needs_verification: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    mandatory: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
