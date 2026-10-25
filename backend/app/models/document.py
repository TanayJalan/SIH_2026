"""Uploaded document model."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.application import Application
from app.models.enums import DocumentVerificationStatus
from app.models.types import enum_type
from app.models.user import User


class Document(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A supporting document attached to an application."""

    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint(
            "application_id",
            "doc_type",
            "version",
            name="uq_documents_application_doc_version",
        ),
        CheckConstraint("version >= 1", name="version_positive"),
        CheckConstraint("size_bytes >= 0", name="size_bytes_non_negative"),
    )

    application_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    doc_type: Mapped[str] = mapped_column(String(100), nullable=False)
    doc_code: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    """APH document code from the Annexure-1/2 checklist."""
    signed_with_dsc: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    """All uploads must be digitally signed; no DSC means no submission (APH 1.4.3)."""
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    """Certificate validity used by the document-expiry alerts."""
    affidavit_no: Mapped[str | None] = mapped_column(String(64), nullable=True)
    """Affidavit or format number, for example Affidavit 2 or Format 3."""
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(
        String(100), nullable=False, default="application/octet-stream",
        server_default="application/octet-stream",
    )
    size_bytes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    verification_status: Mapped[DocumentVerificationStatus] = mapped_column(
        enum_type(DocumentVerificationStatus, "document_verification_status", length=16),
        nullable=False,
        default=DocumentVerificationStatus.PENDING,
        server_default=DocumentVerificationStatus.PENDING.value,
        index=True,
    )
    verification_notes: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )

    application: Mapped[Application] = relationship(back_populates="documents")
    uploader: Mapped[User] = relationship(back_populates="uploaded_documents")
