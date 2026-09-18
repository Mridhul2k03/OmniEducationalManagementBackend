from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from apps.students.models import Student
from apps.students.serializers import StudentSerializer, StudentAdmissionSerializer
from apps.accounts.permissions import HasTenantPermission, IsTenantMember
from apps.audit.services import log_audit_event


class StudentViewSet(viewsets.ModelViewSet):
    """
    Student endpoints strictly scoped to the active tenant.
    Supports search, filtering, and admission workflow.
    """
    queryset = Student.objects.none()
    serializer_class = StudentSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["status", "gender", "blood_group"]
    search_fields = ["admission_number", "first_name", "last_name"]
    ordering_fields = ["admission_number", "first_name", "created_at"]
    ordering = ["admission_number"]

    def get_permissions(self):
        if self.action in ["create", "admit"]:
            return [HasTenantPermission("students.create")()]
        elif self.action in ["update", "partial_update"]:
            return [HasTenantPermission("students.update")()]
        elif self.action == "destroy":
            return [HasTenantPermission("students.delete")()]
        return [HasTenantPermission("students.view")()]

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        if getattr(self, "swagger_fake_view", False) or not tenant:
            return Student.objects.none()
        return Student.objects.filter(tenant=tenant).prefetch_related("guardian_links__guardian")

    @action(detail=False, methods=["post"], url_path="admit")
    def admit(self, request):
        """
        Executes the multi-step admission workflow.
        """
        serializer = StudentAdmissionSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        student = serializer.save()
        return Response(
            {
                "success": True,
                "message": f"Student '{student.full_name}' admitted successfully.",
                "data": StudentSerializer(student).data,
            },
            status=status.HTTP_201_CREATED,
        )

    def perform_destroy(self, instance):
        log_audit_event(
            action="DELETE",
            resource_type="Student",
            resource_id=str(instance.id),
            tenant=self.request.tenant,
            actor=self.request.user,
            description=f"Student {instance.full_name} ({instance.admission_number}) soft-deleted.",
            request=self.request,
        )
        instance.soft_delete()
