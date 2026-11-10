"""Unit tests for the legacy/canonical region matching helper."""

from __future__ import annotations

from dataclasses import dataclass

from app.models.enums import InstitutionRegion
from app.services.regions import institution_region_labels, matches_institution_region


@dataclass(frozen=True)
class _Institution:
    region: str | None
    aicte_region: InstitutionRegion | None


def test_labels_include_city_and_aicte_region() -> None:
    institution = _Institution(region="Pune", aicte_region=InstitutionRegion.WESTERN)

    assert institution_region_labels(institution) == ("Pune", "WESTERN")


def test_missing_region_labels_are_skipped() -> None:
    institution = _Institution(region=None, aicte_region=InstitutionRegion.SOUTHERN)

    assert institution_region_labels(institution) == ("SOUTHERN",)


def test_matching_accepts_either_label_and_rejects_others() -> None:
    institution = _Institution(region="Pune", aicte_region=InstitutionRegion.WESTERN)

    assert matches_institution_region("Pune", institution)
    assert matches_institution_region("WESTERN", institution)
    assert not matches_institution_region("EASTERN", institution)
    assert not matches_institution_region(None, institution)
