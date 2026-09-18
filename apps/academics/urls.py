from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.academics.views import (
    AcademicYearViewSet,
    TermViewSet,
    DepartmentViewSet,
    CourseViewSet,
    SubjectViewSet,
    ClassCohortViewSet,
    SectionViewSet,
)

router = DefaultRouter()
router.register(r"years", AcademicYearViewSet, basename="academic-year")
router.register(r"terms", TermViewSet, basename="academic-term")
router.register(r"departments", DepartmentViewSet, basename="academic-department")
router.register(r"courses", CourseViewSet, basename="academic-course")
router.register(r"subjects", SubjectViewSet, basename="academic-subject")
router.register(r"classes", ClassCohortViewSet, basename="academic-class")
router.register(r"sections", SectionViewSet, basename="academic-section")

urlpatterns = [
    path("", include(router.urls)),
]
