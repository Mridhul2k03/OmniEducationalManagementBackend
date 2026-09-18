from django.urls import path
from apps.common.views import HealthCheckView, ReadinessCheckView

urlpatterns = [
    path("health/", HealthCheckView.as_view(), name="health-check"),
    path("ready/", ReadinessCheckView.as_view(), name="readiness-check"),
]
