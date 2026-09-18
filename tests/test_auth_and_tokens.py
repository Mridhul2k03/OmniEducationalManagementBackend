"""
Authentication, Identity, and JWT Token Test Suite.
"""
import pytest
from rest_framework import status
from rest_framework.test import APIClient
from apps.tenants.models import Tenant
from apps.accounts.models import User, Membership
from tests.conftest import get_auth_client


def test_register_institution_flow():
    """
    Test the public onboarding endpoint:
    - Atomically creates Tenant, Admin User, Admin Role, bootstraps permissions, and returns JWT tokens.
    """
    client = APIClient()
    payload = {
        "email": "chancellor@horizon-edu.org",
        "password": "SuperSecretPassword123!",
        "first_name": "Eleanor",
        "last_name": "Vance",
        "institution_name": "Horizon International University",
        "institution_type": "university",
        "slug": "horizon-intl",
    }

    response = client.post("/api/v1/auth/register-institution/", payload, format="json")
    assert response.status_code == status.HTTP_201_CREATED

    data = response.json()
    assert data["success"] is True
    assert "tokens" in data["data"]
    assert "access" in data["data"]["tokens"]
    assert data["data"]["user"]["email"] == "chancellor@horizon-edu.org"
    assert data["data"]["tenant"]["slug"] == "horizon-intl"

    # Verify database state
    tenant = Tenant.objects.get(slug="horizon-intl")
    assert tenant.status == Tenant.STATUS_ACTIVE
    user = User.objects.get(email="chancellor@horizon-edu.org")
    assert user.is_active is True
    membership = Membership.objects.get(user=user, tenant=tenant)
    assert membership.status == Membership.STATUS_ACTIVE
    assert "students.create" in membership.get_permissions()


def test_login_and_token_refresh(tenant_a, tenant_a_admin):
    """
    Test user authentication, access token issuance, and token refresh.
    """
    client = APIClient()

    # 1. Login
    login_resp = client.post(
        "/api/v1/auth/login/",
        {"email": "principal@oakridge.edu", "password": "SecureAdminPass123!"},
        format="json",
    )
    assert login_resp.status_code == status.HTTP_200_OK
    data = login_resp.json()
    assert "access" in data
    assert "refresh" in data
    assert data["user"]["email"] == "principal@oakridge.edu"
    assert len(data["accessible_tenants"]) >= 1

    refresh_token = data["refresh"]
    access_token = data["access"]

    # 2. Authenticated Profile View (/api/v1/auth/me/)
    auth_client = APIClient()
    auth_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
    auth_client.defaults["HTTP_X_TENANT_ID"] = str(tenant_a.id)

    me_resp = auth_client.get("/api/v1/auth/me/")
    assert me_resp.status_code == status.HTTP_200_OK
    me_data = me_resp.json()["data"]
    assert me_data["user"]["email"] == "principal@oakridge.edu"
    assert me_data["active_tenant"]["id"] == str(tenant_a.id)

    # 3. Token Refresh
    refresh_resp = client.post(
        "/api/v1/auth/refresh/",
        {"refresh": refresh_token},
        format="json",
    )
    assert refresh_resp.status_code == status.HTTP_200_OK
    assert "access" in refresh_resp.json()


def test_switch_tenant_flow(tenant_a, tenant_b, tenant_a_admin):
    """
    Test user switching active organization context.
    """
    # Grant tenant_a_admin membership in tenant_b as well
    Membership.objects.create(
        user=tenant_a_admin,
        tenant=tenant_b,
        status=Membership.STATUS_ACTIVE,
        is_default=False,
    )

    client = get_auth_client(tenant_a_admin, tenant=tenant_a)

    # Switch to tenant_b
    switch_resp = client.post(
        "/api/v1/auth/switch-tenant/",
        {"tenant_id": str(tenant_b.id)},
        format="json",
    )
    assert switch_resp.status_code == status.HTTP_200_OK
    assert switch_resp.json()["data"]["active_tenant"]["id"] == str(tenant_b.id)
