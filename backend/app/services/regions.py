"""Region matching helpers shared by assignment and authorization.

Institutions keep two region fields: the legacy free-text ``region`` (a city in
the demo dataset, and what the UI displays) and the canonical ``aicte_region``
enum. Users in regional and committee roles carry the AICTE region, while
institution admins carry their institution's city. Matching both labels keeps
the older city-based rows working while making the canonical AICTE region
authoritative for assignment.
"""

from __future__ import annotations

from typing import Protocol


class _HasRegion(Protocol):
    region: str | None
    aicte_region: object | None


def institution_region_labels(institution: _HasRegion) -> tuple[str, ...]:
    """Return every non-empty region label an institution can match."""
    labels: list[str] = []
    if institution.region:
        labels.append(institution.region)
    canonical = getattr(institution.aicte_region, "value", institution.aicte_region)
    if canonical and canonical not in labels:
        labels.append(str(canonical))
    return tuple(labels)


def matches_institution_region(region: str | None, institution: _HasRegion) -> bool:
    """Return whether ``region`` names the institution's city or AICTE region."""
    return bool(region) and region in institution_region_labels(institution)
