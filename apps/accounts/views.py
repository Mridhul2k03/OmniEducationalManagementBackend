"""
Authentication, Identity, and RBAC views.
"""
from rest_framework import generics, viewsets, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from apps.accounts.models import User, Membership, Role, Permission
from apps.accounts.serializers import (
    UserSerializer,
    MembershipSerializer,
    RoleSerializer,
    PermissionSerializer,
    CustomTokenObtainPairSerializer,
    RegisterInstitutionSerializer,
)
from apps.accounts.permissions import IsInstitutionAdmin, IsTenantMember
from apps.audit.services import log_audit_event


class RegisterInstitutionView(APIView):
    """
    Public onboarding endpoint: Registers a new institution and initial administrator.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RegisterInstitutionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        return Response(
            {
                "success": True,
                "message": "Institution registered successfully.",
                "data": result,
            },
            status=status.HTTP_201_CREATED,
        )


from django.conf import settings


def set_auth_cookies(response, access_token=None, refresh_token=None):
    """
    Sets HttpOnly cookies on the response for cookie-based authentication.
    """
    secure = not settings.DEBUG
    samesite = "Lax"
    if access_token:
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            secure=secure,
            samesite=samesite,
            max_age=3600,
            path="/",
        )
    if refresh_token:
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=secure,
            samesite=samesite,
            max_age=7 * 86400,
            path="/",
        )
    return response


class CustomLoginView(TokenObtainPairView):
    """
    User login issuing JWT access/refresh tokens with accessible tenant memberships,
    and setting secure HttpOnly authentication cookies.
    """
    serializer_class = CustomTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            access_token = response.data.get("access")
            refresh_token = response.data.get("refresh")
            set_auth_cookies(response, access_token=access_token, refresh_token=refresh_token)
        return response


class CustomTokenRefreshView(TokenRefreshView):
    """
    Refreshes access token, reading refresh token from request body or cookie,
    and updating the HttpOnly access_token cookie.
    """
    def post(self, request, *args, **kwargs):
        data = request.data.copy() if hasattr(request.data, "copy") else dict(request.data)
        if not data.get("refresh") and "refresh_token" in request.COOKIES:
            data["refresh"] = request.COOKIES["refresh_token"]
            request._full_data = data

        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            access_token = response.data.get("access")
            refresh_token = response.data.get("refresh")
            set_auth_cookies(response, access_token=access_token, refresh_token=refresh_token)
        return response


class LogoutView(APIView):
    """
    Logs out the user and clears all auth cookies.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        response = Response({
            "success": True,
            "message": "Logged out successfully."
        }, status=status.HTTP_200_OK)
        response.delete_cookie("access_token", path="/")
        response.delete_cookie("refresh_token", path="/")
        response.delete_cookie("sessionid", path="/")
        return response


class MeView(APIView):
    """
    Returns the currently authenticated user's profile, active tenant, and memberships.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from apps.accounts.permissions import get_or_resolve_tenant

        user = request.user
        tenant = get_or_resolve_tenant(request)

        memberships = Membership.objects.filter(
            user=user,
            status=Membership.STATUS_ACTIVE,
            is_deleted=False,
        ).select_related("tenant")

        active_membership = None
        if tenant:
            active_membership = memberships.filter(tenant=tenant).first()

        accessible_tenants = []
        if user.is_superuser:
            all_tenants = Tenant.objects.filter(is_deleted=False)
            for t in all_tenants:
                accessible_tenants.append({
                    "id": str(t.id),
                    "name": t.name,
                    "slug": t.slug,
                    "institution_type": t.institution_type,
                    "currency": t.currency,
                    "timezone": t.timezone,
                    "is_default": str(t.id) == str(tenant.id) if tenant else False,
                })
        else:
            for m in memberships:
                accessible_tenants.append({
                    "id": str(m.tenant.id),
                    "name": m.tenant.name,
                    "slug": m.tenant.slug,
                    "institution_type": m.tenant.institution_type,
                    "currency": m.tenant.currency,
                    "timezone": m.tenant.timezone,
                    "is_default": m.is_default,
                })

        return Response({
            "success": True,
            "data": {
                "user": UserSerializer(user).data,
                "active_tenant": {
                    "id": str(tenant.id) if tenant else None,
                    "name": tenant.name if tenant else None,
                    "slug": tenant.slug if tenant else None,
                    "institution_type": tenant.institution_type if tenant else "school",
                    "currency": tenant.currency if tenant else "USD",
                    "timezone": tenant.timezone if tenant else "UTC",
                } if tenant else None,
                "active_permissions": ["*"] if user.is_superuser else (list(active_membership.get_permissions()) if active_membership else []),
                "memberships": MembershipSerializer(memberships, many=True).data,
                "accessible_tenants": accessible_tenants,
            }
        })


class SwitchTenantView(APIView):
    """
    Switches the active tenant context for the user by validating membership and setting it as default.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        tenant_id = request.data.get("tenant_id")
        if not tenant_id:
            return Response(
                {"success": False, "error": {"code": "MISSING_TENANT_ID", "message": "tenant_id is required."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        import uuid
        try:
            tenant_uuid = uuid.UUID(str(tenant_id).strip())
            membership_filter = {"tenant_id": tenant_uuid}
        except (ValueError, AttributeError):
            membership_filter = {"tenant__slug": str(tenant_id).strip().lower()}

        membership = Membership.objects.filter(
            user=request.user,
            status=Membership.STATUS_ACTIVE,
            is_deleted=False,
            **membership_filter,
        ).select_related("tenant").first()

        if not membership and not request.user.is_superuser:
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "CROSS_TENANT_FORBIDDEN",
                        "message": "You do not have an active membership with this organization.",
                    },
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Set as default membership
        Membership.objects.filter(user=request.user).update(is_default=False)
        if membership:
            membership.is_default = True
            membership.save(update_fields=["is_default"])

        return Response({
            "success": True,
            "message": f"Active organization switched to {membership.tenant.name if membership else 'selected tenant'}.",
            "data": {
                "active_tenant": {
                    "id": str(membership.tenant.id) if membership else str(tenant_id),
                    "name": membership.tenant.name if membership else "Tenant",
                    "slug": membership.tenant.slug if membership else "",
                }
            }
        })


class RoleViewSet(viewsets.ModelViewSet):
    """
    Role management scoped to the active tenant.
    """
    queryset = Role.objects.none()
    serializer_class = RoleSerializer
    permission_classes = [IsInstitutionAdmin]

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        if getattr(self, "swagger_fake_view", False) or not tenant:
            return Role.objects.none()
        # Return tenant-specific roles and system roles
        return Role.objects.filter(
            tenant=tenant,
            is_deleted=False,
        ) | Role.objects.filter(tenant=None, is_system_role=True)

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.tenant)


class MembershipViewSet(viewsets.ModelViewSet):
    """
    Manage user memberships and role assignments within the active tenant.
    """
    queryset = Membership.objects.none()
    serializer_class = MembershipSerializer
    permission_classes = [IsInstitutionAdmin]

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        if getattr(self, "swagger_fake_view", False) or not tenant:
            return Membership.objects.none()
        return Membership.objects.filter(
            tenant=tenant,
            is_deleted=False,
        ).select_related("user", "tenant")


class PermissionListView(generics.ListAPIView):
    """
    Catalog of all available permissions in the system.
    """
    queryset = Permission.objects.all()
    serializer_class = PermissionSerializer
    permission_classes = [IsTenantMember]
