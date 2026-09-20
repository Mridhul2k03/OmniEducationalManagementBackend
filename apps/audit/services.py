"""
Audit logging service for non-intrusive recording of critical mutations.
"""
from typing import Optional, Dict, Any
from apps.audit.models import AuditLog
from apps.common.context import get_current_request_id, get_current_tenant


def log_audit_event(
    action: str,
    resource_type: str,
    resource_id: str,
    actor=None,
    tenant=None,
    changes: Optional[Dict[str, Any]] = None,
    description: str = "",
    request=None,
) -> AuditLog:
    """
    Creates an immutable audit log record.
    Automatically captures request_id, IP address, and active tenant context.
    """
    if tenant is None:
        tenant = get_current_tenant()

    request_id = get_current_request_id() or ""
    ip_address = None
    user_agent = ""

    if request:
        if actor is None and hasattr(request, "user") and request.user.is_authenticated:
            actor = request.user
        if tenant is None and hasattr(request, "tenant"):
            tenant = request.tenant

        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip_address = x_forwarded_for.split(",")[0].strip()
        else:
            ip_address = request.META.get("REMOTE_ADDR")

        user_agent = request.META.get("HTTP_USER_AGENT", "")[:500]

    # Guard against AnonymousUser or invalid actor instances
    if actor is not None and (not getattr(actor, "is_authenticated", False) or not getattr(actor, "id", None)):
        actor = None

    return AuditLog.objects.create(
        tenant=tenant,
        actor=actor,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id),
        description=description,
        changes=changes or {},
        ip_address=ip_address,
        user_agent=user_agent,
        request_id=request_id,
    )
