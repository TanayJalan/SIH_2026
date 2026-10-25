"""Pydantic schemas for committee selection API responses.

APH clause: APH 1.8a (Scrutiny), APH 1.9a (EVC), APH Annexure-16.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ExpertPoolOut(BaseModel):
    """Public representation of one expert-pool entry."""

    id: uuid.UUID
    name: str
    designation: str
    institution_name: str | None
    state: str
    aicte_region: str
    seat_tags: list[str]
    years_experience: int
    is_retired_hc_judge: bool
    is_active: bool
    is_fictional: bool
    notes: str | None
    recent_assignment_count: int
    apH_clause: str

    model_config = {"from_attributes": True}


class SeatSelectionOut(BaseModel):
    """One seat in a committee selection result."""

    expert_id: uuid.UUID
    expert_name: str
    seat_label: str
    seat_role: str
    reasons: list[str]


class CommitteeSelectionOut(BaseModel):
    """Full response for one committee selection (application or complaint)."""

    committee_id: uuid.UUID
    committee_type: str
    selection_seed: str = Field(
        description="SHA-256 derived seed for reproducible selection (APH 1.8a)."
    )
    seats: list[SeatSelectionOut]
    co_opted: SeatSelectionOut | None = None
    quorum_required: int
    quorum_description: str = ""
    quorum_met: bool
    warnings: list[str]
    status: str
    mode: str
    scheduled_at: datetime | None
    selected_at: datetime | None


class CommitteeSelectRequest(BaseModel):
    """Request body for POST /committees/select."""

    application_id: uuid.UUID | None = None
    complaint_id: uuid.UUID | None = None
    committee_type: str = Field(
        description="CommitteeType value: SCRUTINY, RE_SCRUTINY, EVC, SHC, SAC, SCSC."
    )
    include_co_opt: bool = False
    selection_seed: str | None = Field(
        default=None,
        description="Override seed for replay/audit. Leave blank for a fresh selection.",
    )
    scheduled_at: datetime | None = None
    mode: str = "ONLINE"


class QuorumCheckOut(BaseModel):
    """Response for quorum check endpoint."""

    committee_type: str
    present_count: int
    quorum_required: int
    quorum_description: str
    quorum_met: bool
    apH_clause: str
