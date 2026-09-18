"""
Root URL Configuration for OmniEducationalManagement backend.
Exposes versioned REST API (/api/v1/) and OpenAPI documentation.
"""
from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)

api_v1_patterns = [
    # Health and Liveness Probes
    path("", include("apps.common.urls")),
    # Identity, Authentication & RBAC
    path("", include("apps.accounts.urls")),
    # Multi-Tenant / Organization Management
    path("tenants/", include("apps.tenants.urls")),
    # Academic Structure (Years, Terms, Classes, Subjects)
    path("academics/", include("apps.academics.urls")),
    # Students and Admissions
    path("students/", include("apps.students.urls")),
    # Staff and Faculty
    path("staff/", include("apps.staff.urls")),
    # Attendance Tracking
    path("attendance/", include("apps.attendance.urls")),
    # Examinations, Grading and Marks
    path("exams/", include("apps.examinations.urls")),
    # Finance, Fees, Invoices and Payments
    path("finance/", include("apps.finance.urls")),
    # Announcements & Notifications
    path("communications/", include("apps.communications.urls")),
    # Audit Logs
    path("audit/", include("apps.audit.urls")),
    # OpenAPI 3.0 Documentation
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include(api_v1_patterns)),
]
