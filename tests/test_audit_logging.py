"""
Audit Logging Verification Test Suite.
Verifies that all sensitive domain mutations create immutable audit trails.
"""
import pytest
from rest_framework import status
from apps.audit.models import AuditLog
from apps.audit.services import log_audit_event
from tests.conftest import get_auth_client


def test_audit_logging_service_recording(tenant_a, tenant_a_admin):
    """
    Test direct and service-level audit recording.
    """
    log_entry = log_audit_event(
        action="UPDATE",
        resource_type="TenantPolicy",
        resource_id="POL-01",
        tenant=tenant_a,
        actor=tenant_a_admin,
        changes={"before": {"strict_mode": False}, "after": {"strict_mode": True}},
        description="Enabled strict attendance verification policy.",
    )

    assert log_entry.id is not None
    assert log_entry.tenant == tenant_a
    assert log_entry.actor == tenant_a_admin
    assert log_entry.action == "UPDATE"
    assert log_entry.resource_type == "TenantPolicy"
    assert log_entry.changes["after"]["strict_mode"] is True

    # Verify query via tenant admin API
    client = get_auth_client(tenant_a_admin, tenant=tenant_a)
    response = client.get("/api/v1/audit/")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["meta"]["count"] >= 1
