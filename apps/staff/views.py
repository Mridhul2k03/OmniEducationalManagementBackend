from rest_framework import viewsets, filters, permissions
from django_filters.rest_framework import DjangoFilterBackend
from apps.staff.models import Staff
from apps.staff.serializers import StaffSerializer
from apps.accounts.permissions import HasTenantPermission


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
        tenant = getattr(self.request, "tenant", None)
        if getattr(self, "swagger_fake_view", False) or not tenant:
            return Staff.objects.none()
        return Staff.objects.filter(tenant=tenant).select_related("user", "department")

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.tenant)
