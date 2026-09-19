"""
Tests for Platform SuperAdmin Control Center.
Verifies role access control (IsSuperAdmin), user management, tenant onboarding, password resets, and metrics.
"""
import pytest
from rest_framework import status
from apps.accounts.models import User, Membership, Role
from apps.tenants.models import Tenant
from tests.conftest import get_auth_client


def test_platform_admin_requires_superadmin(tenant_a_admin, super_admin_user):
    """
    Standard institution admins and users must be blocked (403) from platform-admin endpoints.
    Only superadmins can access them.
    """
    # 1. Standard institution admin attempts access
    tenant_admin_client = get_auth_client(tenant_a_admin)
    res = tenant_admin_client.get("/api/v1/platform-admin/stats/")
    assert res.status_code == status.HTTP_403_FORBIDDEN

    res_users = tenant_admin_client.get("/api/v1/platform-admin/users/")
    assert res_users.status_code == status.HTTP_403_FORBIDDEN

    # 2. Superadmin accesses stats
    super_client = get_auth_client(super_admin_user)
    res_super = super_client.get("/api/v1/platform-admin/stats/")
    assert res_super.status_code == status.HTTP_200_OK
    assert "tenants" in res_super.data["data"]
    assert "users" in res_super.data["data"]
    assert res_super.data["data"]["users"]["superadmins"] >= 1


def test_platform_user_crud_and_password_reset(super_admin_user, tenant_a):
    """
    SuperAdmin can create a user across the platform, toggle their active state,
    reset their password, and assign them to a tenant.
    """
    client = get_auth_client(super_admin_user)

    # 1. Create a new platform user
    create_payload = {
        "email": "new.instructor@test-platform.org",
        "password": "InitialPassword123!",
        "first_name": "Alexander",
        "last_name": "Hamilton",
        "tenant_id": str(tenant_a.id),
        "role_code": "faculty",
    }
    res_create = client.post("/api/v1/platform-admin/users/", create_payload, format="json")
    assert res_create.status_code == status.HTTP_201_CREATED
    user_id = res_create.data["id"]

    # Verify user was created in DB and assigned to tenant_a
    user_obj = User.objects.get(id=user_id)
    assert user_obj.email == "new.instructor@test-platform.org"
    assert user_obj.memberships.filter(tenant=tenant_a).exists()

    # 2. Toggle user active state (suspend)
    res_toggle = client.post(f"/api/v1/platform-admin/users/{user_id}/toggle-status/")
    assert res_toggle.status_code == status.HTTP_200_OK
    user_obj.refresh_from_db()
    assert user_obj.is_active is False

    # 3. Reset user password
    res_reset = client.post(
        f"/api/v1/platform-admin/users/{user_id}/reset-password/",
        {"new_password": "NewSuperSecretPassword123!"},
        format="json",
    )
    assert res_reset.status_code == status.HTTP_200_OK
    user_obj.refresh_from_db()
    assert user_obj.check_password("NewSuperSecretPassword123!") is True

    # 4. Filter users by active state
    res_list = client.get("/api/v1/platform-admin/users/?is_active=false")
    assert res_list.status_code == status.HTTP_200_OK
    users_list = res_list.data.get("data", res_list.data.get("results", []))
    assert any(u["id"] == user_id for u in users_list)


def test_platform_tenant_onboarding_and_lifecycle(super_admin_user):
    """
    SuperAdmin can provision a new institution tenant with an initial administrator,
    update its plan, and toggle its active/suspended lifecycle.
    """
    client = get_auth_client(super_admin_user)

    # 1. Onboard a new tenant
    tenant_payload = {
        "name": "Cambridge Innovation Academy",
        "legal_name": "Cambridge Innovation Academy LLC",
        "slug": "cambridge-academy",
        "institution_type": "school",
        "currency": "GBP",
        "timezone": "Europe/London",
        "contact_email": "info@cambridge-academy.uk",
        "subscription_plan": "Enterprise",
        "admin_email": "principal@cambridge-academy.uk",
        "admin_password": "CambridgeAdmin123!",
        "admin_first_name": "Evelyn",
        "admin_last_name": "Wright",
    }
    res_onboard = client.post("/api/v1/platform-admin/tenants/", tenant_payload, format="json")
    assert res_onboard.status_code == status.HTTP_201_CREATED
    tenant_id = res_onboard.data["id"]

    # Verify tenant exists
    tenant_obj = Tenant.objects.get(id=tenant_id)
    assert tenant_obj.slug == "cambridge-academy"
    assert tenant_obj.status == Tenant.STATUS_ACTIVE

    # Verify admin user was provisioned
    admin_user = User.objects.get(email="principal@cambridge-academy.uk")
    assert admin_user.memberships.filter(tenant=tenant_obj).exists()

    # 2. Update tenant configuration
    res_update = client.patch(
        f"/api/v1/platform-admin/tenants/{tenant_id}/",
        {"legal_name": "Cambridge Global Educational Trust", "subscription_reference": "Enterprise-Plus"},
        format="json",
    )
    assert res_update.status_code == status.HTTP_200_OK
    tenant_obj.refresh_from_db()
    assert tenant_obj.legal_name == "Cambridge Global Educational Trust"

    # 3. Toggle status to suspended
    res_toggle = client.post(f"/api/v1/platform-admin/tenants/{tenant_id}/toggle-status/")
    assert res_toggle.status_code == status.HTTP_200_OK
    tenant_obj.refresh_from_db()
    assert tenant_obj.status == Tenant.STATUS_SUSPENDED
