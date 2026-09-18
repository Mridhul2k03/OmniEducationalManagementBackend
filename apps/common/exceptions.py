"""
Centralized exception handling for Django REST Framework.
Standardizes all API error responses into a consistent JSON envelope.
"""
from datetime import datetime, timezone
import logging
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import (
    APIException,
    ValidationError,
    AuthenticationFailed,
    NotAuthenticated,
    PermissionDenied,
    NotFound,
    MethodNotAllowed,
)
from apps.common.context import get_current_request_id

logger = logging.getLogger(__name__)


class CrossTenantForbiddenException(PermissionDenied):
    default_detail = "Cross-tenant access forbidden. You are not an active member of this organization."
    default_code = "CROSS_TENANT_FORBIDDEN"


def custom_exception_handler(exc, context):
    """
    Custom exception handler that returns a uniform JSON envelope for all API errors:
    {
        "success": false,
        "error": {
            "code": "ERROR_CODE",
            "message": "Human readable error message",
            "details": {...}
        },
        "meta": {
            "request_id": "...",
            "timestamp": "..."
        }
    }
    """
    # Call REST framework's default exception handler first to get standard response
    response = exception_handler(exc, context)

    request_id = get_current_request_id()
    now_iso = datetime.now(timezone.utc).isoformat()

    if response is not None:
        error_code = "API_ERROR"
        message = "An error occurred while processing your request."
        details = {}

        if isinstance(exc, ValidationError):
            error_code = "VALIDATION_ERROR"
            message = "Input validation failed. Please check the provided fields."
            details = response.data
        elif isinstance(exc, (AuthenticationFailed, NotAuthenticated)):
            error_code = "AUTHENTICATION_REQUIRED"
            message = getattr(exc, "detail", "Authentication credentials were not provided or are invalid.")
            if isinstance(message, dict):
                details = message
                message = "Authentication failed."
        elif isinstance(exc, CrossTenantForbiddenException):
            error_code = "CROSS_TENANT_FORBIDDEN"
            message = str(exc.detail)
        elif isinstance(exc, PermissionDenied):
            error_code = "PERMISSION_DENIED"
            message = getattr(exc, "detail", "You do not have permission to perform this action.")
            if isinstance(message, dict):
                details = message
                message = "Permission denied."
        elif isinstance(exc, NotFound):
            error_code = "NOT_FOUND"
            message = getattr(exc, "detail", "The requested resource was not found.")
        elif isinstance(exc, MethodNotAllowed):
            error_code = "METHOD_NOT_ALLOWED"
            message = f"Method '{context.get('request').method}' not allowed."
        else:
            if hasattr(exc, "default_code"):
                error_code = str(exc.default_code).upper()
            if isinstance(response.data, dict):
                details = response.data
                message = response.data.get("detail", message)
            elif isinstance(response.data, list):
                details = {"errors": response.data}

        response.data = {
            "success": False,
            "error": {
                "code": error_code,
                "message": str(message),
                "details": details if details else None,
            },
            "meta": {
                "request_id": request_id,
                "timestamp": now_iso,
            },
        }
        return response

    # Unhandled exceptions (e.g. 500 server error)
    logger.exception(f"Unhandled exception occurred. RequestID: {request_id}", exc_info=exc)

    return Response(
        {
            "success": False,
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected internal server error occurred. Our engineering team has been notified.",
                "details": None,
            },
            "meta": {
                "request_id": request_id,
                "timestamp": now_iso,
            },
        },
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
