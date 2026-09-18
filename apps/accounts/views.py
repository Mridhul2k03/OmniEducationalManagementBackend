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


class CustomLoginView(TokenObtainPairView):
    """
    User login issuing JWT access/refresh tokens with accessible tenant memberships.
    """
    serializer_class = CustomTokenObtainPairSerializer


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

        return Response({
            "success": True,
            "data": {
                "user": UserSerializer(user).data,
                "active_tenant": {
                    "id": str(tenant.id) if tenant else None,
                    "name": tenant.name if tenant else None,
                    "slug": tenant.slug if tenant else None,
                } if tenant else None,
                "active_permissions": list(active_membership.get_permissions()) if active_membership else [],
                "memberships": MembershipSerializer(memberships, many=True).data,
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

        membership = Membership.objects.filter(
            user=request.user,
            tenant_id=tenant_id,
            status=Membership.STATUS_ACTIVE,
            is_deleted=False,
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
