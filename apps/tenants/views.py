from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from apps.tenants.models import Tenant
from apps.tenants.serializers import TenantSerializer, TenantDetailSerializer
from apps.accounts.permissions import IsSuperAdmin, IsInstitutionAdmin
from apps.audit.services import log_audit_event


class TenantViewSet(viewsets.ModelViewSet):
    """
    Tenant management.
    List/Retrieve: accessible to members for their tenant, or superadmins for all.
    Update: accessible to Institution Admins and Superadmins.
    Create/Delete: restricted to Superadmins or onboarding flow.
    """
    queryset = Tenant.objects.all()
    lookup_field = "id"

    def get_serializer_class(self):
        if self.action in ["retrieve", "update", "partial_update"]:
            return TenantDetailSerializer
        return TenantSerializer

    def get_permissions(self):
        if self.action in ["create", "destroy"]:
            return [IsSuperAdmin()]
        elif self.action in ["update", "partial_update"]:
            return [IsInstitutionAdmin()]
        elif self.action == "list":
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        if not self.request.user or not self.request.user.is_authenticated:
            return Tenant.objects.filter(is_deleted=False, status=Tenant.STATUS_ACTIVE)
        if self.request.user.is_superuser:
            return Tenant.objects.filter(is_deleted=False)
        # Return only tenants where the user has an active membership
        return Tenant.objects.filter(
            memberships__user=self.request.user,
            memberships__status="active",
            is_deleted=False,
        ).distinct()

    def perform_update(self, serializer):
        instance = serializer.save()
        log_audit_event(
            action="UPDATE",
            resource_type="Tenant",
            resource_id=str(instance.id),
            tenant=instance,
            actor=self.request.user,
            changes=serializer.validated_data,
            description=f"Tenant '{instance.name}' configuration updated.",
            request=self.request,
        )

    @action(detail=False, methods=["get"], permission_classes=[permissions.IsAuthenticated])
    def current(self, request):
        """
        Returns the active tenant context for the current request.
        """
        from apps.accounts.permissions import get_or_resolve_tenant
        tenant = getattr(request, "tenant", None) or get_or_resolve_tenant(request)
        if not tenant:
            return Response(
                {"success": False, "error": {"code": "NO_ACTIVE_TENANT", "message": "No active tenant selected."}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = TenantDetailSerializer(tenant)
        return Response({"success": True, "data": serializer.data})
