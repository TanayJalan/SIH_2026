"""Institution summaries shared by API responses."""

import uuid

from pydantic import BaseModel, ConfigDict


class InstitutionSummary(BaseModel):
    """Public fields describing an institution."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    state: str
    region: str
