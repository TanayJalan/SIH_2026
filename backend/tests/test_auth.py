"""Authentication endpoint tests."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.security import decode_access_token
from app.db.session import SessionLocal
from app.models.audit import AuditLog
from app.models.enums import Role
from tests.support import TestData, login

ROLE_CASES = [
    ("institution_admin_west", Role.INSTITUTION_ADMIN),
    ("scrutiny", Role.SCRUTINY_COMMITTEE_MEMBER),
    ("inspection", Role.EVC_MEMBER),
    ("regional", Role.REGIONAL_OFFICER),
    ("regulation", Role.REGULATION_BUREAU_OFFICER),
    ("shc", Role.SHC_MEMBER),
    ("sac", Role.SAC_MEMBER),
    ("ec", Role.EXECUTIVE_COMMITTEE_MEMBER),
    ("complaints", Role.COMPLAINT_SCRUTINY_MEMBER),
    ("super", Role.SUPER_ADMIN),
]


@pytest.mark.parametrize(("user_key", "expected_role"), ROLE_CASES)
def test_all_ten_roles_can_log_in_and_read_their_profile(
    api_client: TestClient,
    test_data: TestData,
    user_key: str,
    expected_role: Role,
) -> None:
    user = test_data.users[user_key]
    response = api_client.post(
        "/auth/login",
        json={"email": user.email, "password": test_data.password},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 8 * 60 * 60
    assert body["user"]["role"] == expected_role.value
    assert body["user"]["id"] == str(user.id)

    settings = get_settings()
    claims = decode_access_token(
        token=body["access_token"],
        secret_key=settings.secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )
    assert claims["role"] == expected_role.value
    assert claims["institution_id"] == (
        str(user.institution_id) if user.institution_id is not None else None
    )
    assert claims["exp"] - claims["iat"] == 8 * 60 * 60

    profile = api_client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {body['access_token']}"},
    )
    assert profile.status_code == 200
    assert profile.json()["email"] == user.email
    assert profile.json()["role"] == expected_role.value


def test_login_creates_audit_row(
    api_client: TestClient,
    test_data: TestData,
) -> None:
    user = test_data.users["institution_admin_west"]
    login(api_client, user.email, test_data.password)

    with SessionLocal() as db:
        entry = db.scalars(
            select(AuditLog)
            .where(
                AuditLog.action == "auth.login",
                AuditLog.actor_id == user.id,
            )
            .order_by(AuditLog.created_at.desc())
        ).first()

    assert entry is not None
    assert entry.entity_type == "User"
    assert entry.entity_id == user.id
    assert entry.after is not None
    assert entry.after["email"] == user.email
    assert entry.ip is not None


def test_login_rejects_wrong_password_and_does_not_audit_success(
    api_client: TestClient,
    test_data: TestData,
) -> None:
    user = test_data.users["institution_admin_west"]
    with SessionLocal() as db:
        before = db.scalar(
            select(func.count())
            .select_from(AuditLog)
            .where(AuditLog.actor_id == user.id, AuditLog.action == "auth.login")
        )

    response = api_client.post(
        "/auth/login",
        json={"email": user.email, "password": "definitely-the-wrong-password"},
    )

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert response.json()["detail"] == "Invalid email or password"

    with SessionLocal() as db:
        after = db.scalar(
            select(func.count())
            .select_from(AuditLog)
            .where(AuditLog.actor_id == user.id, AuditLog.action == "auth.login")
        )
    assert after == before


def test_protected_endpoints_require_a_valid_bearer_token(
    api_client: TestClient,
) -> None:
    unauthenticated = api_client.get("/auth/me")
    assert unauthenticated.status_code == 401

    malformed = api_client.get(
        "/auth/me",
        headers={"Authorization": "Bearer not-a-jwt"},
    )
    assert malformed.status_code == 401
    assert malformed.json()["detail"] == "Could not validate credentials"
