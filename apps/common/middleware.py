"""
Middlewares for Request ID correlation and Multi-Tenant context isolation.
"""
import uuid
import json
from django.utils.deprecation import MiddlewareMixin
from django.http import JsonResponse
from apps.common.context import (
    set_current_request_id,
    get_current_request_id,
    set_current_tenant,
    clear_current_tenant,
)


class RequestIDMiddleware(MiddlewareMixin):
    """
    Assigns or preserves an X-Request-ID header for tracing and correlation across logs.
    """
    def process_request(self, request):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.request_id = request_id
        set_current_request_id(request_id)

    def process_response(self, request, response):
        request_id = getattr(request, "request_id", None) or get_current_request_id()
        if request_id:
            response["X-Request-ID"] = request_id
        return response


class TenantContextMiddleware(MiddlewareMixin):
    """
    Resolves the tenant context for authenticated users.
    Enforces strict membership verification. Never trusts arbitrary client tenant IDs.
    """
    def process_request(self, request):
        clear_current_tenant()
        request.tenant = None

        # If user is not yet authenticated by Django session, check Authorization: Bearer JWT header
        if not hasattr(request, "user") or not request.user.is_authenticated:
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                try:
                    from rest_framework_simplejwt.authentication import JWTAuthentication
                    raw_token = auth_header.split(" ")[1]
                    jwt_auth = JWTAuthentication()
                    validated_token = jwt_auth.get_validated_token(raw_token)
                    request.user = jwt_auth.get_user(validated_token)
                except Exception:
                    pass

        if not hasattr(request, "user") or not request.user.is_authenticated:
            return None

        # Deferred import to avoid circular dependencies
        from apps.accounts.models import Membership
        from apps.tenants.models import Tenant

        raw_tenant_id = request.headers.get("X-Tenant-ID")
        requested_tenant_id = str(raw_tenant_id).strip() if raw_tenant_id else None
        if requested_tenant_id in ("", "null", "undefined", "None"):
            requested_tenant_id = None

        if requested_tenant_id:
            try:
                # Check if provided identifier is a valid UUID
                tenant_uuid = uuid.UUID(requested_tenant_id)
                superuser_lookup = {"id": tenant_uuid}
                membership_lookup = {"tenant_id": tenant_uuid}
            except (ValueError, AttributeError):
                # Fallback to resolving by slug (e.g. 'oxford-crest')
                tenant_slug = requested_tenant_id.lower()
                superuser_lookup = {"slug": tenant_slug}
                membership_lookup = {"tenant__slug": tenant_slug}

            # Superusers can access any active tenant
            if request.user.is_superuser:
                tenant = Tenant.objects.filter(**superuser_lookup, is_deleted=False).first()
                if not tenant:
                    return JsonResponse(
                        {
                            "success": False,
                            "error": {
                                "code": "TENANT_NOT_FOUND",
                                "message": "The requested organization does not exist.",
                                "details": None,
                            },
                            "meta": {"request_id": getattr(request, "request_id", None)}
                        },
                        status=404,
                    )
                request.tenant = tenant
                set_current_tenant(tenant)
                return None

            # Verify that the user has an active membership for the requested tenant
            membership = Membership.objects.filter(
                user=request.user,
                status=Membership.STATUS_ACTIVE,
                is_deleted=False,
                **membership_lookup,
            ).select_related("tenant").first()

            if not membership:
                return JsonResponse(
                    {
                        "success": False,
                        "error": {
                            "code": "CROSS_TENANT_FORBIDDEN",
                            "message": "Cross-tenant access forbidden. You are not an active member of this organization.",
                            "details": None,
                        },
                        "meta": {
                            "request_id": getattr(request, "request_id", None),
                        }
                    },
                    status=403,
                )

            request.tenant = membership.tenant
            set_current_tenant(membership.tenant)

        else:
            # No X-Tenant-ID header provided: resolve user's primary/default active membership
            membership = Membership.objects.filter(
                user=request.user,
                status=Membership.STATUS_ACTIVE,
                is_deleted=False,
            ).select_related("tenant").order_by("-is_default", "-joined_at").first()

            if membership:
                request.tenant = membership.tenant
                set_current_tenant(membership.tenant)

        return None

    def process_response(self, request, response):
        clear_current_tenant()
        return response

    def process_exception(self, request, exception):
        clear_current_tenant()
        return None
