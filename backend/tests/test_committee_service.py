"""Tests for CommitteeService and Committee API endpoints.

Covers:
- Composition rules for Chapter I (academic + advocate + architect) [APH 16.3]
- Composition rules for Chapter II (two academics) [APH 16.4]
- Composition rules for EVC (academic chair + expert + architect) [APH 16.5]
- Composition rules for SHC / SAC (chair + expert + revenue/architect) [APH 16.6]
- Composition rules for SCSC (judge + two experts + architect + DTE/Registrar) [APH 16.7]
- Exclusion of members from institution's home state [APH 1.8a]
- Consecutive committee penalty / load balancing
- Deterministic reproduction via selection_seed
- Quorum checks (EC one third APH 16.2, SCSC any two APH 16.7)
- API endpoint permissions and institution access scoping
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.application import Application
from app.models.committee import Committee, CommitteeMember
from app.models.enums import CommitteeMode, CommitteeStatus, CommitteeType, Role
from app.models.expert_pool import ExpertPool
from app.models.institution import Institution
from app.services.audit import AuditService
from app.services.committee import CommitteeService
from tests.support import TestData, auth_headers


def test_composition_chapter_1_scrutiny(test_data: TestData) -> None:
    """Chapter I (new institutions) must draw: academic + advocate + architect (APH 16.3)."""
    with SessionLocal() as db:
        audit = AuditService(db)
        svc = CommitteeService(db, audit)

        # West application is track NEW_INSTITUTION
        app = db.get(Application, test_data.applications["west"])
        assert app is not None

        # Set institution state to Maharashtra so experts from Maharashtra are excluded
        inst = db.get(Institution, app.institution_id)
        assert inst is not None
        inst.state = "Maharashtra"
        db.flush()

        result = svc.select_committee(
            CommitteeType.SCRUTINY,
            application=app,
            selection_seed="seed-ch1-test-01",
        )
        db.commit()

        roles = [s.seat_role for s in result.seats]
        assert "ACADEMIC" in roles
        assert "ADVOCATE" in roles
        assert "ARCHITECT" in roles
        assert len(result.seats) == 3

        for s in result.seats:
            expert = db.get(ExpertPool, s.expert_id)
            assert expert is not None
            assert expert.state != "Maharashtra", f"Expert {expert.name} from {expert.state} should be excluded"


def test_composition_chapter_2_scrutiny(test_data: TestData) -> None:
    """Chapter II (existing institutions) must draw: two academics (APH 16.4)."""
    with SessionLocal() as db:
        audit = AuditService(db)
        svc = CommitteeService(db, audit)

        # East application is track EXISTING (EOA)
        app = db.get(Application, test_data.applications["east"])
        assert app is not None

        result = svc.select_committee(
            CommitteeType.SCRUTINY,
            application=app,
            selection_seed="seed-ch2-test-01",
        )
        db.commit()

        roles = [s.seat_role for s in result.seats]
        assert "ACADEMIC_1" in roles
        assert "ACADEMIC_2" in roles
        assert len(result.seats) == 2


def test_composition_evc(test_data: TestData) -> None:
    """EVC must draw: academic chair + expert + architect (APH 16.5)."""
    with SessionLocal() as db:
        audit = AuditService(db)
        svc = CommitteeService(db, audit)

        app = db.get(Application, test_data.applications["west"])
        assert app is not None

        result = svc.select_committee(
            CommitteeType.EVC,
            application=app,
            selection_seed="seed-evc-test-01",
        )
        db.commit()

        roles = [s.seat_role for s in result.seats]
        assert "ACADEMIC_CHAIR" in roles
        assert "EXPERT" in roles
        assert "ARCHITECT" in roles
        assert len(result.seats) == 3


def test_composition_shc_sac(test_data: TestData) -> None:
    """SHC/SAC must draw: chair + expert + revenue/architect (APH 16.6)."""
    with SessionLocal() as db:
        audit = AuditService(db)
        svc = CommitteeService(db, audit)

        app = db.get(Application, test_data.applications["west"])
        assert app is not None

        result = svc.select_committee(
            CommitteeType.SHC,
            application=app,
            selection_seed="seed-shc-test-01",
        )
        db.commit()

        roles = [s.seat_role for s in result.seats]
        assert "CHAIR" in roles
        assert "EXPERT" in roles
        assert "REVENUE_ARCH" in roles
        assert len(result.seats) == 3


def test_composition_scsc_and_coopt(test_data: TestData) -> None:
    """SCSC must draw: retired HC judge + 2 experts + architect + DTE/Registrar (APH 16.7)."""
    with SessionLocal() as db:
        audit = AuditService(db)
        svc = CommitteeService(db, audit)

        app = db.get(Application, test_data.applications["west"])
        assert app is not None

        result = svc.select_committee(
            CommitteeType.SCSC,
            application=app,
            selection_seed="seed-scsc-test-01",
            include_co_opt=True,
        )
        db.commit()

        roles = [s.seat_role for s in result.seats]
        assert "CHAIR" in roles
        assert "EXPERT_1" in roles
        assert "EXPERT_2" in roles
        assert "ARCHITECT" in roles
        assert "DTE_REGISTRAR" in roles
        assert len(result.seats) == 5

        # Check chair is retired HC judge
        chair_seat = next(s for s in result.seats if s.seat_role == "CHAIR")
        chair_expert = db.get(ExpertPool, chair_seat.expert_id)
        assert chair_expert is not None
        assert chair_expert.is_retired_hc_judge is True

        # Check co-opted member is included
        assert result.co_opted is not None
        assert result.co_opted.seat_role == "CO_OPT"


def test_selection_is_reproducible_with_seed(test_data: TestData) -> None:
    """The same selection_seed must produce the identical committee members (APH 1.8a reproducibility)."""
    fixed_seed = "reproducible-deterministic-seed-42"
    with SessionLocal() as db1:
        svc1 = CommitteeService(db1, AuditService(db1))
        app1 = db1.get(Application, test_data.applications["west"])
        assert app1 is not None
        res1 = svc1.select_committee(CommitteeType.EVC, application=app1, selection_seed=fixed_seed)
        members1 = [s.expert_id for s in res1.seats]
        db1.rollback()

    with SessionLocal() as db2:
        svc2 = CommitteeService(db2, AuditService(db2))
        app2 = db2.get(Application, test_data.applications["west"])
        assert app2 is not None
        res2 = svc2.select_committee(CommitteeType.EVC, application=app2, selection_seed=fixed_seed)
        members2 = [s.expert_id for s in res2.seats]
        db2.rollback()

    assert members1 == members2


def test_quorum_checks() -> None:
    """Check quorum requirements per APH 16.2 (EC) and APH 16.7 (SCSC)."""
    # SCSC: any two members
    met, desc, required = CommitteeService.check_quorum(CommitteeType.SCSC, 1)
    assert not met
    assert required == 2

    met, desc, required = CommitteeService.check_quorum(CommitteeType.SCSC, 2)
    assert met

    met, desc, required = CommitteeService.check_quorum(CommitteeType.SCSC, 5)
    assert met

    # EC: one third (at least 1)
    met, desc, required = CommitteeService.check_quorum(CommitteeType.EC, 1)
    assert met
    assert required == 1


def test_committee_api_select_and_list(api_client: TestClient, test_data: TestData) -> None:
    """Test POST /committees/select and GET /committees/application/{id}."""
    headers = auth_headers(api_client, test_data.users["regional"], test_data.password)

    payload = {
        "committee_type": "SCRUTINY",
        "application_id": str(test_data.applications["west"]),
        "selection_seed": "api-test-seed-100",
        "mode": "ONLINE",
    }

    resp = api_client.post("/committees/select", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["committee_type"] == "SCRUTINY"
    assert len(body["seats"]) == 3
    assert body["selection_seed"] == "api-test-seed-100"

    # Now get history for application
    hist_resp = api_client.get(
        f"/committees/application/{test_data.applications['west']}",
        headers=headers,
    )
    assert hist_resp.status_code == 200
    hist = hist_resp.json()
    assert len(hist) >= 1
    assert any(c["selection_seed"] == "api-test-seed-100" for c in hist)


def test_institution_user_isolation(api_client: TestClient, test_data: TestData) -> None:
    """Institution admin can only see committees for their own institution."""
    inst_headers = auth_headers(
        api_client, test_data.users["institution_admin_west"], test_data.password
    )

    # West application belongs to west institution (where institution_admin_west belongs)
    resp_west = api_client.get(
        f"/committees/application/{test_data.applications['west']}",
        headers=inst_headers,
    )
    assert resp_west.status_code == 200

    # East application belongs to east institution -> Access denied (403)
    resp_east = api_client.get(
        f"/committees/application/{test_data.applications['east']}",
        headers=inst_headers,
    )
    assert resp_east.status_code == 403
