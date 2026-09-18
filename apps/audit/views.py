from rest_framework import generics, filters
from django_filters.rest_framework import DjangoFilterBackend
from apps.audit.models import AuditLog
from apps.audit.serializers import AuditLogSerializer
from apps.accounts.permissions import IsInstitutionAdmin


class AuditLogListView(generics.ListAPIView):
    """
    List audit logs scoped strictly to the active tenant.
    Only accessible by Institution Admins and Super Admins.
    """
    queryset = AuditLog.objects.none()
    serializer_class = AuditLogSerializer
    permission_classes = [IsInstitutionAdmin]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["action", "resource_type", "actor"]
    search_fields = ["resource_id", "description", "request_id", "actor__email"]
    ordering_fields = ["created_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return AuditLog.objects.none()
        if self.request.user.is_superuser and not getattr(self.request, "tenant", None):
            return AuditLog.objects.all().select_related("actor", "tenant")
        tenant = getattr(self.request, "tenant", None)
        if not tenant:
            return AuditLog.objects.none()
        return AuditLog.objects.filter(tenant=tenant).select_related("actor")
