"""
Role-Based Access Control (RBAC) and Tenant Scoped Permission classes for DRF.
"""
import uuid
from rest_framework.permissions import BasePermission
from apps.accounts.models import Membership, Role
from apps.tenants.models import Tenant
from apps.common.context import set_current_tenant


def get_or_resolve_tenant(request):
    """
    Safely retrieves or lazily resolves the active tenant for the request.
    """
    tenant = getattr(request, "tenant", None)
    if tenant:
        return tenant

    if not (hasattr(request, "user") and request.user and request.user.is_authenticated):
        return None

    raw_tenant_id = request.headers.get("X-Tenant-ID")
    requested_tenant_id = str(raw_tenant_id).strip() if raw_tenant_id else None
    if requested_tenant_id in ("", "null", "undefined", "None"):
        requested_tenant_id = None

    if requested_tenant_id:
        try:
            tenant_uuid = uuid.UUID(requested_tenant_id)
            superuser_lookup = {"id": tenant_uuid}
            membership_lookup = {"tenant_id": tenant_uuid}
        except (ValueError, AttributeError):
            tenant_slug = requested_tenant_id.lower()
            superuser_lookup = {"slug": tenant_slug}
            membership_lookup = {"tenant__slug": tenant_slug}

        if request.user.is_superuser:
            tenant = Tenant.objects.filter(**superuser_lookup, is_deleted=False).first()
            if tenant:
                request.tenant = tenant
                set_current_tenant(tenant)
                return tenant
            return None

        membership = Membership.objects.filter(
            user=request.user,
            status=Membership.STATUS_ACTIVE,
            is_deleted=False,
            **membership_lookup,
        ).select_related("tenant").first()
    else:
        membership = Membership.objects.filter(
            user=request.user,
            status=Membership.STATUS_ACTIVE,
            is_deleted=False,
        ).select_related("tenant").order_by("-is_default", "-joined_at").first()

    if membership:
        request.tenant = membership.tenant
        set_current_tenant(membership.tenant)
        return membership.tenant

    # If user is superuser with no direct membership, fallback to default active tenant
    if request.user.is_superuser:
        tenant = Tenant.objects.filter(is_deleted=False, status=Tenant.STATUS_ACTIVE).first() or Tenant.objects.filter(is_deleted=False).first()
        if tenant:
            request.tenant = tenant
            set_current_tenant(tenant)
            return tenant

    return None


class IsSuperAdmin(BasePermission):
    """
    Allows access only to global platform superadmins.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_superuser)


class IsTenantMember(BasePermission):
    """
    Allows access only to users who are active members of the current tenant context.
    """
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        tenant = get_or_resolve_tenant(request)
        if request.user.is_superuser:
            return True
        return bool(tenant is not None)


class IsInstitutionAdmin(BasePermission):
    """
    Allows access to institution administrators or principals of the current tenant.
    """
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        tenant = get_or_resolve_tenant(request)
        if request.user.is_superuser:
            return True
        if not tenant:
            return False

        return Membership.objects.filter(
            user=request.user,
            tenant=tenant,
            status=Membership.STATUS_ACTIVE,
            membership_roles__role__code__in=[
                Role.CODE_INSTITUTION_ADMIN,
                Role.CODE_SUPER_ADMIN,
            ],
            is_deleted=False,
        ).exists()


def HasTenantPermission(required_permission_code: str):
    """
    Permission factory returning a BasePermission class checking for a specific permission code.
    Example: permission_classes = [HasTenantPermission('students.view')]
    """
    class TenantPermissionCheck(BasePermission):
        permission_code = required_permission_code

        def has_permission(self, request, view):
            if not (request.user and request.user.is_authenticated):
                return False
            
            # Always ensure tenant context is resolved on request
            tenant = get_or_resolve_tenant(request)

            if request.user.is_superuser:
                return True

            if not tenant:
                return False

            membership = Membership.objects.filter(
                user=request.user,
                tenant=tenant,
                status=Membership.STATUS_ACTIVE,
                is_deleted=False,
            ).first()

            if not membership:
                return False

            # Institution Admin has full access to their tenant
            has_admin_role = membership.membership_roles.filter(
                role__code__in=[Role.CODE_INSTITUTION_ADMIN, Role.CODE_SUPER_ADMIN]
            ).exists()
            if has_admin_role:
                return True

            # Check granular permission code
            return self.permission_code in membership.get_permissions()

        def __call__(self):
            return self

    return TenantPermissionCheck
