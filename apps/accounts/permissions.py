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
    Allows access only to global platform superadmins (is_superuser=True).
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_superuser)


class IsTenantMember(BasePermission):
    """
    Allows access to authenticated members of the active tenant context.
    """
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.user.is_superuser:
            return True
        tenant = get_or_resolve_tenant(request)
        return bool(tenant is not None)


class IsInstitutionSuperAdmin(BasePermission):
    """
    Allows access to Institution Super Admins (full control over the institution)
    or Global Platform Superadmins.
    """
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.user.is_superuser:
            return True

        tenant = get_or_resolve_tenant(request)
        if not tenant:
            return False

        return Membership.objects.filter(
            user=request.user,
            tenant=tenant,
            status=Membership.STATUS_ACTIVE,
            membership_roles__role__code__in=[
                Role.CODE_INSTITUTION_SUPER_ADMIN,
                Role.CODE_SUPER_ADMIN,
            ],
            is_deleted=False,
        ).exists()


class IsInstitutionAdmin(BasePermission):
    """
    Allows access to Institution Super Admins or Delegated Institution Admins of the current tenant.
    """
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.user.is_superuser:
            return True

        tenant = get_or_resolve_tenant(request)
        if not tenant:
            return False

        return Membership.objects.filter(
            user=request.user,
            tenant=tenant,
            status=Membership.STATUS_ACTIVE,
            membership_roles__role__code__in=[
                Role.CODE_INSTITUTION_SUPER_ADMIN,
                Role.CODE_INSTITUTION_ADMIN,
                Role.CODE_SUPER_ADMIN,
            ],
            is_deleted=False,
        ).exists()


def HasTenantPermission(required_permission_code: str):
    """
    Permission factory returning a BasePermission class checking for a specific permission code.
    Institution Super Admins always possess all permissions within their tenant.
    Example: permission_classes = [HasTenantPermission('students.view')]
    """
    class TenantPermissionCheck(BasePermission):
        permission_code = required_permission_code

        def has_permission(self, request, view):
            if not (request.user and request.user.is_authenticated):
                return False

            if request.user.is_superuser:
                return True

            tenant = get_or_resolve_tenant(request)
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

            # Institution Super Admin has wildcard full control over all tenant capabilities
            is_super = membership.membership_roles.filter(
                role__code__in=[Role.CODE_INSTITUTION_SUPER_ADMIN, Role.CODE_SUPER_ADMIN]
            ).exists()
            if is_super:
                return True

            # Delegated admin / staff: verify specific permission code
            user_perms = membership.get_permissions()
            if "*" in user_perms or self.permission_code in user_perms:
                return True

            return False

        def __call__(self):
            return self

    return TenantPermissionCheck


def is_user_institution_superadmin(user, tenant) -> bool:
    """
    Returns True if user is a global superuser or holds the institution_super_admin role in the given tenant.
    """
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if not tenant:
        return False
    return Membership.objects.filter(
        user=user,
        tenant=tenant,
        status=Membership.STATUS_ACTIVE,
        membership_roles__role__code__in=[Role.CODE_INSTITUTION_SUPER_ADMIN, Role.CODE_SUPER_ADMIN],
        is_deleted=False,
    ).exists()

