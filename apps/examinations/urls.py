from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.examinations.views import (
    GradeScaleViewSet,
    ExamViewSet,
    ExamSubjectViewSet,
    MarkViewSet,
)

router = DefaultRouter()
router.register(r"grade-scales", GradeScaleViewSet, basename="grade-scale")
router.register(r"exams", ExamViewSet, basename="exam")
router.register(r"schedules", ExamSubjectViewSet, basename="exam-schedule")
router.register(r"marks", MarkViewSet, basename="mark")

urlpatterns = [
    path("", include(router.urls)),
]
