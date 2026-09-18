"""
Health and readiness check views for container orchestration and uptime monitoring.
"""
from datetime import datetime, timezone
from django.db import connection
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from apps.common.context import get_current_request_id


class HealthCheckView(APIView):
    """
    Liveness probe: verifies application is running.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({
            "success": True,
            "data": {
                "status": "healthy",
                "service": "OmniEducationalManagementBackend",
                "version": "1.0.0",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            "meta": {
                "request_id": get_current_request_id(),
            }
        })


class ReadinessCheckView(APIView):
    """
    Readiness probe: verifies database connectivity and core services.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        db_healthy = True
        error_msg = None
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
        except Exception as e:
            db_healthy = False
            error_msg = str(e)

        status_code = 200 if db_healthy else 503
        return Response(
            {
                "success": db_healthy,
                "data": {
                    "database": "connected" if db_healthy else "unhealthy",
                    "error": error_msg,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
                "meta": {
                    "request_id": get_current_request_id(),
                }
            },
            status=status_code,
        )
