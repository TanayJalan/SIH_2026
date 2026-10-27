"""Uploaded document model."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.application import Application
from app.models.deficiency import Deficiency
from app.models.enums import DocumentRejectionReason, DocumentVerificationStatus
from app.models.types import enum_type
from app.models.user import User


class Document(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A supporting document attached to an application.

    Every upload is an immutable version. A reviewer may reject or flag a
    document; the institution then uploads a new version and the earlier row is
    kept, marked ``superseded_by`` and still downloadable (APH 1.4.3, 1.8f).
    """

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
    rejection_reason_code: Mapped[DocumentRejectionReason | None] = mapped_column(
        enum_type(DocumentRejectionReason, "document_rejection_reason", length=24),
        nullable=True,
    )
    rejection_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    rejected_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    rejected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    apH_clause: Mapped[str | None] = mapped_column(String(64), nullable=True)
    """APH clause for the review decision, for example ``APH 1.8f``."""
    superseded_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    related_deficiency_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("deficiencies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    signer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    """Name of the person whose DSC signed the upload (APH 1.4.3)."""

    application: Mapped[Application] = relationship(back_populates="documents")
    uploader: Mapped[User] = relationship(
        back_populates="uploaded_documents", foreign_keys=[uploaded_by]
    )
    rejector: Mapped[User | None] = relationship(
        back_populates="rejected_documents", foreign_keys=[rejected_by]
    )
    superseding_document: Mapped[Document | None] = relationship(
        foreign_keys=[superseded_by]
    )
    related_deficiency: Mapped[Deficiency | None] = relationship(
        foreign_keys=[related_deficiency_id]
    )

