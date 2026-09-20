import pytest
from rest_framework.test import APIClient
from apps.accounts.models import User, Membership, Role, Permission, RolePermission, MembershipRole
from apps.tenants.models import Tenant
from apps.staff.models import Staff
from apps.accounts.serializers import bootstrap_tenant_roles_and_permissions


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def sample_tenant(db):
    tenant = Tenant.objects.create(
        name="Apex Academy",
        slug="apex-academy",
        status=Tenant.STATUS_ACTIVE,
        institution_type=Tenant.TYPE_COLLEGE,
        contact_email="admin@apex.edu",
    )
    bootstrap_tenant_roles_and_permissions(tenant)
    return tenant


@pytest.fixture
def institution_super_admin(db, sample_tenant):
    user = User.objects.create_user(
        email="superadmin@apex.edu",
        password="Password123!",
        first_name="Arthur",
        last_name="SuperAdmin",
    )
    membership = Membership.objects.create(
        user=user,
        tenant=sample_tenant,
        status=Membership.STATUS_ACTIVE,
        is_default=True,
    )
    role = Role.objects.get(tenant=sample_tenant, code=Role.CODE_INSTITUTION_SUPER_ADMIN)
    MembershipRole.objects.create(membership=membership, role=role)
    return user, membership


@pytest.fixture
def delegated_admin(db, sample_tenant):
    user = User.objects.create_user(
        email="delegated.admin@apex.edu",
        password="Password123!",
        first_name="David",
        last_name="Delegated",
    )
    membership = Membership.objects.create(
        user=user,
        tenant=sample_tenant,
        status=Membership.STATUS_ACTIVE,
        is_default=True,
    )
    role = Role.objects.get(tenant=sample_tenant, code=Role.CODE_INSTITUTION_ADMIN)
    MembershipRole.objects.create(membership=membership, role=role)
    return user, membership


@pytest.fixture
def faculty_user(db, sample_tenant):
    user = User.objects.create_user(
        email="teacher@apex.edu",
        password="Password123!",
        first_name="Prof",
        last_name="Euler",
    )
    membership = Membership.objects.create(
        user=user,
        tenant=sample_tenant,
        status=Membership.STATUS_ACTIVE,
        is_default=True,
    )
    role = Role.objects.get(tenant=sample_tenant, code="faculty")
    MembershipRole.objects.create(membership=membership, role=role)
    return user, membership


@pytest.mark.django_db
def test_institution_super_admin_can_create_delegated_admin(api_client, sample_tenant, institution_super_admin):
    user, _ = institution_super_admin
    api_client.force_authenticate(user=user)

    url = "/api/v1/institution-users/"
    payload = {
        "email": "branch.admin@apex.edu",
        "first_name": "Branch",
        "last_name": "Manager",
        "role_code": "institution_admin",
        "designation": "Branch Operations Admin",
    }
    response = api_client.post(url, payload, HTTP_X_TENANT_ID=str(sample_tenant.id))
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["email"] == "branch.admin@apex.edu"
    assert data["primary_role"]["code"] == "institution_admin"


@pytest.mark.django_db
def test_delegated_admin_cannot_create_super_admin(api_client, sample_tenant, delegated_admin):
    user, _ = delegated_admin
    api_client.force_authenticate(user=user)

    url = "/api/v1/institution-users/"
    payload = {
        "email": "unauthorized.super@apex.edu",
        "first_name": "Rogue",
        "last_name": "Admin",
        "role_code": "institution_super_admin",
    }
    response = api_client.post(url, payload, HTTP_X_TENANT_ID=str(sample_tenant.id))
    assert response.status_code == 403


@pytest.mark.django_db
def test_delegated_admin_cannot_deactivate_super_admin(api_client, sample_tenant, delegated_admin, institution_super_admin):
    del_user, _ = delegated_admin
    _, super_membership = institution_super_admin
    api_client.force_authenticate(user=del_user)

    url = f"/api/v1/institution-users/{super_membership.id}/toggle-status/"
    response = api_client.post(url, HTTP_X_TENANT_ID=str(sample_tenant.id))
    assert response.status_code == 403


@pytest.mark.django_db
def test_super_admin_can_deactivate_and_activate_staff(api_client, sample_tenant, institution_super_admin, faculty_user):
    super_user, _ = institution_super_admin
    _, faculty_membership = faculty_user
    api_client.force_authenticate(user=super_user)

    url = f"/api/v1/institution-users/{faculty_membership.id}/toggle-status/"
    # 1. Deactivate
    res1 = api_client.post(url, HTTP_X_TENANT_ID=str(sample_tenant.id))
    assert res1.status_code == 200
    faculty_membership.refresh_from_db()
    assert faculty_membership.status == Membership.STATUS_SUSPENDED
    assert faculty_membership.user.is_active is False

    # 2. Reactivate
    res2 = api_client.post(url, HTTP_X_TENANT_ID=str(sample_tenant.id))
    assert res2.status_code == 200
    faculty_membership.refresh_from_db()
    assert faculty_membership.status == Membership.STATUS_ACTIVE
    assert faculty_membership.user.is_active is True


@pytest.mark.django_db
def test_super_admin_can_reset_user_password(api_client, sample_tenant, institution_super_admin, faculty_user):
    super_user, _ = institution_super_admin
    fac_user, faculty_membership = faculty_user
    api_client.force_authenticate(user=super_user)

    url = f"/api/v1/institution-users/{faculty_membership.id}/reset-password/"
    res = api_client.post(url, {"new_password": "NewSecretPassword123!"}, HTTP_X_TENANT_ID=str(sample_tenant.id))
    assert res.status_code == 200

    fac_user.refresh_from_db()
    assert fac_user.check_password("NewSecretPassword123!") is True
