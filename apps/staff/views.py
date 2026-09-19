from rest_framework import viewsets, filters, permissions
from django_filters.rest_framework import DjangoFilterBackend
from apps.staff.models import Staff
from apps.staff.serializers import StaffSerializer
from apps.accounts.permissions import HasTenantPermission, get_or_resolve_tenant
from apps.audit.services import log_audit_event


class StaffViewSet(viewsets.ModelViewSet):
    """
    Staff / Faculty endpoints strictly scoped to the active tenant.
    """
    queryset = Staff.objects.none()
    serializer_class = StaffSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["status", "employment_type", "department"]
    search_fields = ["employee_id", "user__first_name", "user__last_name", "designation"]
    ordering_fields = ["employee_id", "joined_date", "created_at"]
    ordering = ["employee_id"]

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [HasTenantPermission("staff.manage")()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        tenant = get_or_resolve_tenant(self.request)
        if getattr(self, "swagger_fake_view", False) or not tenant:
            return Staff.objects.none()
        return Staff.objects.filter(tenant=tenant).select_related("user", "department")

    def perform_create(self, serializer):
        tenant = get_or_resolve_tenant(self.request)
        staff = serializer.save(tenant=tenant)
        log_audit_event(
            action="CREATE",
            resource_type="Staff",
            resource_id=str(staff.id),
            actor=self.request.user,
            tenant=tenant,
            description=f"Added staff member {staff.user.full_name or staff.user.email} (ID: {staff.employee_id})",
            changes={"employee_id": staff.employee_id, "designation": staff.designation, "email": staff.user.email},
            request=self.request,
        )

    def perform_update(self, serializer):
        tenant = get_or_resolve_tenant(self.request)
        staff = serializer.save()
        log_audit_event(
            action="UPDATE",
            resource_type="Staff",
            resource_id=str(staff.id),
            actor=self.request.user,
            tenant=tenant,
            description=f"Updated staff member {staff.user.full_name or staff.user.email} (ID: {staff.employee_id})",
            changes=serializer.validated_data,
            request=self.request,
        )

    def perform_destroy(self, instance):
        tenant = get_or_resolve_tenant(self.request)
        log_audit_event(
            action="DELETE",
            resource_type="Staff",
            resource_id=str(instance.id),
            actor=self.request.user,
            tenant=tenant,
            description=f"Deleted staff member {instance.user.full_name or instance.user.email} (ID: {instance.employee_id})",
            changes={"employee_id": instance.employee_id},
            request=self.request,
        )
        instance.delete()

