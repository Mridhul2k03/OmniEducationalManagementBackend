"""
URLs for Platform SuperAdmin Console.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.platform_admin.views import (
    PlatformUserViewSet,
    PlatformTenantViewSet,
    PlatformAuditLogViewSet,
    PlatformStatsView,
)

router = DefaultRouter()
router.register(r"users", PlatformUserViewSet, basename="platform-user")
router.register(r"tenants", PlatformTenantViewSet, basename="platform-tenant")
router.register(r"audit-logs", PlatformAuditLogViewSet, basename="platform-audit-log")

urlpatterns = [
    path("stats/", PlatformStatsView.as_view(), name="platform-stats"),
    path("", include(router.urls)),
]
