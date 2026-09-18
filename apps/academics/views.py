from rest_framework import viewsets
from apps.academics.models import AcademicYear, Term, Department, Course, Subject, ClassCohort, Section
from apps.academics.serializers import (
    AcademicYearSerializer,
    TermSerializer,
    DepartmentSerializer,
    CourseSerializer,
    SubjectSerializer,
    ClassCohortSerializer,
    SectionSerializer,
)
from apps.accounts.permissions import HasTenantPermission, IsTenantMember


class AcademicYearViewSet(viewsets.ModelViewSet):
    queryset = AcademicYear.objects.none()
    serializer_class = AcademicYearSerializer

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [HasTenantPermission("academics.manage")()]
        return [IsTenantMember()]

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        if getattr(self, "swagger_fake_view", False) or not tenant:
            return AcademicYear.objects.none()
        return AcademicYear.objects.filter(tenant=tenant)

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.tenant, created_by=self.request.user)


class TermViewSet(viewsets.ModelViewSet):
    queryset = Term.objects.none()
    serializer_class = TermSerializer

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [HasTenantPermission("academics.manage")()]
        return [IsTenantMember()]

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        if getattr(self, "swagger_fake_view", False) or not tenant:
            return Term.objects.none()
        return Term.objects.filter(tenant=tenant)

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.tenant, created_by=self.request.user)


class DepartmentViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.none()
    serializer_class = DepartmentSerializer

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [HasTenantPermission("academics.manage")()]
        return [IsTenantMember()]

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        if getattr(self, "swagger_fake_view", False) or not tenant:
            return Department.objects.none()
        return Department.objects.filter(tenant=tenant)

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.tenant, created_by=self.request.user)


class CourseViewSet(viewsets.ModelViewSet):
    queryset = Course.objects.none()
    serializer_class = CourseSerializer

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [HasTenantPermission("academics.manage")()]
        return [IsTenantMember()]

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        if getattr(self, "swagger_fake_view", False) or not tenant:
            return Course.objects.none()
        return Course.objects.filter(tenant=tenant)

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.tenant, created_by=self.request.user)


class SubjectViewSet(viewsets.ModelViewSet):
    queryset = Subject.objects.none()
    serializer_class = SubjectSerializer

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [HasTenantPermission("academics.manage")()]
        return [IsTenantMember()]

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        if getattr(self, "swagger_fake_view", False) or not tenant:
            return Subject.objects.none()
        return Subject.objects.filter(tenant=tenant)

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.tenant, created_by=self.request.user)


class ClassCohortViewSet(viewsets.ModelViewSet):
    queryset = ClassCohort.objects.none()
    serializer_class = ClassCohortSerializer

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [HasTenantPermission("academics.manage")()]
        return [IsTenantMember()]

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        if getattr(self, "swagger_fake_view", False) or not tenant:
            return ClassCohort.objects.none()
        return ClassCohort.objects.filter(tenant=tenant).prefetch_related("sections")

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.tenant, created_by=self.request.user)


class SectionViewSet(viewsets.ModelViewSet):
    queryset = Section.objects.none()
    serializer_class = SectionSerializer

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [HasTenantPermission("academics.manage")()]
        return [IsTenantMember()]

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        if getattr(self, "swagger_fake_view", False) or not tenant:
            return Section.objects.none()
        return Section.objects.filter(tenant=tenant)

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.tenant, created_by=self.request.user)
