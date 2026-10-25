"""User model."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import Role
from app.models.types import enum_type

if TYPE_CHECKING:
    from app.models.alert import Alert
    from app.models.application import Application
    from app.models.audit import AuditLog
    from app.models.decision import CouncilRatification, DecisionLetter
    from app.models.deficiency import Deficiency
    from app.models.document import Document
    from app.models.inspection import Inspection
    from app.models.institution import Institution
    from app.models.workflow import WorkflowEvent


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An authenticated actor in the approval workflow."""

    __tablename__ = "users"
    __table_args__ = (Index("ix_users_role_active", "role", "is_active"),)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[Role] = mapped_column(enum_type(Role, "user_role", length=32), nullable=False)
    institution_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("institutions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    region: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )

    institution: Mapped[Institution | None] = relationship(back_populates="users")
    assigned_applications: Mapped[list[Application]] = relationship(
        back_populates="assigned_officer"
    )
    uploaded_documents: Mapped[list[Document]] = relationship(back_populates="uploader")
    workflow_events: Mapped[list[WorkflowEvent]] = relationship(back_populates="actor")
    raised_deficiencies: Mapped[list[Deficiency]] = relationship(back_populates="raised_by_user")
    inspections: Mapped[list[Inspection]] = relationship(back_populates="committee_member")
    alerts: Mapped[list[Alert]] = relationship(
        back_populates="recipient", foreign_keys="Alert.recipient_user_id"
    )
    audit_logs: Mapped[list[AuditLog]] = relationship(back_populates="actor")
    ratified_decisions: Mapped[list[CouncilRatification]] = relationship(
        back_populates="ratified_by_user",
        foreign_keys="CouncilRatification.ratified_by",
    )
    acknowledged_letters: Mapped[list[DecisionLetter]] = relationship(
        back_populates="acknowledged_by_user",
        foreign_keys="DecisionLetter.acknowledged_by",
    )
