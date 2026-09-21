from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.students.views import StudentViewSet
from apps.students.registration_views import StudentRegistrationRequestViewSet
from apps.students.portal_views import (
    StudentPortalDashboardView,
    StudentPortalTimetableView,
    StudentPortalAttendanceView,
    StudentPortalGradesView,
    StudentPortalInvoicesView,
)

router = DefaultRouter()
router.register(r"registration-requests", StudentRegistrationRequestViewSet, basename="student-registration-request")
router.register(r"", StudentViewSet, basename="student")

urlpatterns = [
    path("portal/dashboard/", StudentPortalDashboardView.as_view(), name="student-portal-dashboard"),
    path("portal/timetable/", StudentPortalTimetableView.as_view(), name="student-portal-timetable"),
    path("portal/attendance/", StudentPortalAttendanceView.as_view(), name="student-portal-attendance"),
    path("portal/grades/", StudentPortalGradesView.as_view(), name="student-portal-grades"),
    path("portal/invoices/", StudentPortalInvoicesView.as_view(), name="student-portal-invoices"),
    path("", include(router.urls)),
]

