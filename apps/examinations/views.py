from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from apps.examinations.models import GradeScale, Exam, ExamSubject, Mark
from apps.examinations.serializers import (
    GradeScaleSerializer,
    ExamSerializer,
    ExamSubjectSerializer,
    MarkSerializer,
)
from apps.examinations.services import publish_exam_results_service
from apps.accounts.permissions import HasTenantPermission, IsTenantMember


class GradeScaleViewSet(viewsets.ModelViewSet):
    queryset = GradeScale.objects.none()
    serializer_class = GradeScaleSerializer
    permission_classes = [IsTenantMember]

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        if getattr(self, "swagger_fake_view", False) or not tenant:
            return GradeScale.objects.none()
        return GradeScale.objects.filter(tenant=tenant)

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.tenant, created_by=self.request.user)


class ExamViewSet(viewsets.ModelViewSet):
    queryset = Exam.objects.none()
    serializer_class = ExamSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["class_cohort", "academic_year", "status", "is_published"]

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [HasTenantPermission("exams.manage")()]
        elif self.action == "publish":
            return [HasTenantPermission("marks.publish")()]
        return [IsTenantMember()]

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        if getattr(self, "swagger_fake_view", False) or not tenant:
            return Exam.objects.none()
        return Exam.objects.filter(tenant=tenant).prefetch_related("exam_subjects__subject")

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.tenant, created_by=self.request.user)

    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        """
        Publishes the exam results and enforces immutability on marks.
        """
        exam = publish_exam_results_service(
            tenant=request.tenant,
            exam_id=pk,
            actor=request.user,
            request=request,
        )
        return Response({
            "success": True,
            "message": f"Examination '{exam.name}' results published successfully.",
            "data": ExamSerializer(exam).data,
        })


class ExamSubjectViewSet(viewsets.ModelViewSet):
    queryset = ExamSubject.objects.none()
    serializer_class = ExamSubjectSerializer

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [HasTenantPermission("exams.manage")()]
        return [IsTenantMember()]

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        if getattr(self, "swagger_fake_view", False) or not tenant:
            return ExamSubject.objects.none()
        return ExamSubject.objects.filter(tenant=tenant).select_related("subject", "exam")

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.tenant, created_by=self.request.user)


class MarkViewSet(viewsets.ModelViewSet):
    queryset = Mark.objects.none()
    serializer_class = MarkSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["exam_subject", "student", "status"]

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update"]:
            return [HasTenantPermission("marks.enter")()]
        elif self.action == "destroy":
            return [HasTenantPermission("exams.manage")()]
        return [IsTenantMember()]

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        if getattr(self, "swagger_fake_view", False) or not tenant:
            return Mark.objects.none()

        user = self.request.user
        qs = Mark.objects.filter(tenant=tenant).select_related(
            "student", "exam_subject__subject", "exam_subject__exam"
        )

        exam_param = self.request.query_params.get("exam") or self.request.query_params.get("exam_id")
        if exam_param:
            qs = qs.filter(exam_subject__exam_id=exam_param)

        # If user is student, only allow seeing their own marks and only for published exams
        if hasattr(user, "student_profile"):
            return qs.filter(student=user.student_profile, exam_subject__exam__is_published=True)

        return qs

    def perform_create(self, serializer):
        serializer.save(
            tenant=self.request.tenant,
            entered_by=self.request.user,
            created_by=self.request.user,
        )

