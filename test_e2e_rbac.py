import os
import sys
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
sys.path.insert(0, os.path.dirname(__file__))
django.setup()

from rest_framework.test import APIClient
from apps.accounts.models import User, Membership, Role, MembershipRole
from apps.tenants.models import Tenant
from apps.accounts.serializers import bootstrap_tenant_roles_and_permissions

client = APIClient()

# 1. Setup Tenant
tenant, _ = Tenant.objects.get_or_create(
    slug="cambridge-crest",
    defaults={
        "name": "Cambridge Crest Academy",
        "institution_type": "college",
        "status": "active",
        "contact_email": "admin@cambridge.edu",
    }
)
bootstrap_tenant_roles_and_permissions(tenant)

# 2. Setup Institution Super Admin
super_user, _ = User.objects.get_or_create(
    email="cambridge.superadmin@edu.org",
    defaults={"first_name": "Eleanor", "last_name": "Vance", "is_active": True}
)
super_user.set_password("Password123!")
super_user.save()

super_mem, _ = Membership.objects.get_or_create(
    user=super_user,
    tenant=tenant,
    defaults={"status": Membership.STATUS_ACTIVE, "is_default": True}
)
super_role = Role.objects.get(tenant=tenant, code=Role.CODE_INSTITUTION_SUPER_ADMIN)
MembershipRole.objects.get_or_create(membership=super_mem, role=super_role)

print("[1] Institution Super Admin Setup: OK")

# 3. Test Super Admin API operations
client.force_authenticate(user=super_user)

# A. Create Delegated Admin
res_admin = client.post(
    "/api/v1/institution-users/",
    {
        "email": "operations.admin@cambridge.edu",
        "first_name": "Marcus",
        "last_name": "Vance",
        "role_code": "institution_admin",
        "designation": "Operations Admin",
        "permissions": ["staff.manage", "students.view", "academics.manage"],
    },
    HTTP_X_TENANT_ID=str(tenant.id),
)
assert res_admin.status_code == 201, f"Expected 201, got {res_admin.status_code}: {res_admin.content}"
print("[2] Super Admin created Delegated Admin: OK")

# B. Create Faculty Member
res_faculty = client.post(
    "/api/v1/institution-users/",
    {
        "email": "math.prof@cambridge.edu",
        "first_name": "Alan",
        "last_name": "Turing",
        "role_code": "faculty",
        "designation": "Senior Professor of Mathematics",
    },
    HTTP_X_TENANT_ID=str(tenant.id),
)
assert res_faculty.status_code == 201, f"Expected 201, got {res_faculty.status_code}: {res_faculty.content}"
faculty_mem_id = res_faculty.json()["data"]["membership_id"]
print("[3] Super Admin created Faculty Member: OK")

# C. Deactivate Faculty Member
res_deact = client.post(
    f"/api/v1/institution-users/{faculty_mem_id}/toggle-status/",
    HTTP_X_TENANT_ID=str(tenant.id),
)
assert res_deact.status_code == 200
assert res_deact.json()["data"]["status"] == "suspended"
print("[4] Super Admin deactivated Faculty Member: OK")

# D. Reactivate Faculty Member
res_act = client.post(
    f"/api/v1/institution-users/{faculty_mem_id}/toggle-status/",
    HTTP_X_TENANT_ID=str(tenant.id),
)
assert res_act.status_code == 200
assert res_act.json()["data"]["status"] == "active"
print("[5] Super Admin reactivated Faculty Member: OK")

# 4. Test Delegated Admin Hierarchy Protection
del_user = User.objects.get(email="operations.admin@cambridge.edu")
client.force_authenticate(user=del_user)

# A. Delegated Admin attempts to deactivate Super Admin -> Expect 403 Forbidden
res_forbidden = client.post(
    f"/api/v1/institution-users/{super_mem.id}/toggle-status/",
    HTTP_X_TENANT_ID=str(tenant.id),
)
assert res_forbidden.status_code == 403, f"Expected 403, got {res_forbidden.status_code}"
print("[6] Delegated Admin blocked from modifying Super Admin (Hierarchy Guard): OK")

# B. Delegated Admin attempts to create another Super Admin -> Expect 403 Forbidden
res_forbidden2 = client.post(
    "/api/v1/institution-users/",
    {
        "email": "hacked.super@cambridge.edu",
        "first_name": "Hacked",
        "last_name": "Super",
        "role_code": "institution_super_admin",
    },
    HTTP_X_TENANT_ID=str(tenant.id),
)
assert res_forbidden2.status_code == 403, f"Expected 403, got {res_forbidden2.status_code}"
print("[7] Delegated Admin blocked from creating Super Admin (Escalation Guard): OK")

print("\nALL RBAC VERIFICATIONS PASSED SUCCESSFULLY!")
