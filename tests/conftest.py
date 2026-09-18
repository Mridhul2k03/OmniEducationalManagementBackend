"""
Pytest configuration, fixtures, and factory helpers for OmniEducationalManagement.
"""
import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.tenants.models import Tenant
from apps.accounts.models import (
    User,
    Membership,
    Role,
    Permission,
    RolePermission,
    MembershipRole,
)
from apps.accounts.serializers import DEFAULT_PERMISSION_DEFINITIONS


@pytest.fixture(autouse=True)
def enable_db_access_for_all_tests(db):
    """Enables database access for all tests."""
    pass


@pytest.fixture
def permissions_catalog():
    """Initializes standard permission catalog."""
    perms = {}
    for code, name, module in DEFAULT_PERMISSION_DEFINITIONS:
        perm, _ = Permission.objects.get_or_create(
            code=code,
            defaults={"name": name, "module": module},
        )
        perms[code] = perm
    return perms


@pytest.fixture
def tenant_a():
    return Tenant.objects.create(
        name="Oakridge International Academy",
        slug="oakridge",
        institution_type=Tenant.TYPE_SCHOOL,
        status=Tenant.STATUS_ACTIVE,
        contact_email="admin@oakridge.edu",
    )


@pytest.fixture
def tenant_b():
    return Tenant.objects.create(
        name="Apex Technical University",
        slug="apex-uni",
        institution_type=Tenant.TYPE_UNIVERSITY,
        status=Tenant.STATUS_ACTIVE,
        contact_email="admin@apex.edu",
    )


@pytest.fixture
def super_admin_user():
    return User.objects.create_superuser(
        email="superadmin@omniplatform.com",
        password="SuperAdminPassword123!",
        first_name="Platform",
        last_name="SuperAdmin",
    )


@pytest.fixture
def tenant_a_admin(tenant_a, permissions_catalog):
    user = User.objects.create_user(
        email="principal@oakridge.edu",
        password="SecureAdminPass123!",
        first_name="Arthur",
        last_name="Pendleton",
    )
    admin_role, _ = Role.objects.get_or_create(
        tenant=tenant_a,
        code=Role.CODE_INSTITUTION_ADMIN,
        defaults={"name": "Institution Administrator", "is_system_role": True},
    )
    for perm in permissions_catalog.values():
        RolePermission.objects.get_or_create(role=admin_role, permission=perm)

    membership = Membership.objects.create(
        user=user,
        tenant=tenant_a,
        status=Membership.STATUS_ACTIVE,
        is_default=True,
    )
    MembershipRole.objects.create(membership=membership, role=admin_role)
    return user


@pytest.fixture
def tenant_b_admin(tenant_b, permissions_catalog):
    user = User.objects.create_user(
        email="dean@apex.edu",
        password="SecureAdminPass123!",
        first_name="Beatrice",
        last_name="Vance",
    )
    admin_role, _ = Role.objects.get_or_create(
        tenant=tenant_b,
        code=Role.CODE_INSTITUTION_ADMIN,
        defaults={"name": "Institution Administrator", "is_system_role": True},
    )
    for perm in permissions_catalog.values():
        RolePermission.objects.get_or_create(role=admin_role, permission=perm)

    membership = Membership.objects.create(
        user=user,
        tenant=tenant_b,
        status=Membership.STATUS_ACTIVE,
        is_default=True,
    )
    MembershipRole.objects.create(membership=membership, role=admin_role)
    return user


@pytest.fixture
def tenant_a_teacher(tenant_a, permissions_catalog):
    user = User.objects.create_user(
        email="teacher@oakridge.edu",
        password="TeacherPass123!",
        first_name="Thomas",
        last_name="Clark",
    )
    teacher_role, _ = Role.objects.get_or_create(
        tenant=tenant_a,
        code=Role.CODE_TEACHER,
        defaults={"name": "Teacher", "is_system_role": True},
    )
    # Assign only attendance and marks entry permissions
    for code in ["attendance.mark", "attendance.view", "marks.enter", "students.view"]:
        if code in permissions_catalog:
            RolePermission.objects.get_or_create(role=teacher_role, permission=permissions_catalog[code])

    membership = Membership.objects.create(
        user=user,
        tenant=tenant_a,
        status=Membership.STATUS_ACTIVE,
        is_default=True,
    )
    MembershipRole.objects.create(membership=membership, role=teacher_role)
    return user


@pytest.fixture
def tenant_a_accountant(tenant_a, permissions_catalog):
    user = User.objects.create_user(
        email="accountant@oakridge.edu",
        password="AccountantPass123!",
        first_name="Alice",
        last_name="Morgan",
    )
    accountant_role, _ = Role.objects.get_or_create(
        tenant=tenant_a,
        code=Role.CODE_ACCOUNTANT,
        defaults={"name": "Accountant", "is_system_role": True},
    )
    for code in ["fees.view", "fees.create_invoice", "fees.record_payment", "fees.refund", "students.view"]:
        if code in permissions_catalog:
            RolePermission.objects.get_or_create(role=accountant_role, permission=permissions_catalog[code])

    membership = Membership.objects.create(
        user=user,
        tenant=tenant_a,
        status=Membership.STATUS_ACTIVE,
        is_default=True,
    )
    MembershipRole.objects.create(membership=membership, role=accountant_role)
    return user


def get_auth_client(user, tenant=None):
    """Helper to return APIClient authenticated with JWT Bearer and optional X-Tenant-ID header."""
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    if tenant:
        client.defaults["HTTP_X_TENANT_ID"] = str(tenant.id)
    return client
