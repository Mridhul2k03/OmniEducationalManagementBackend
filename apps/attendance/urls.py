from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.attendance.views import AttendanceRecordViewSet, AttendanceCorrectionRequestViewSet

router = DefaultRouter()
router.register(r"records", AttendanceRecordViewSet, basename="attendance-record")
router.register(r"corrections", AttendanceCorrectionRequestViewSet, basename="attendance-correction")

urlpatterns = [
    path("", include(router.urls)),
]
