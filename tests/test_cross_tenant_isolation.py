"""
Security & Tenant Isolation Test Suite.
Verifies that multi-tenant boundaries are strictly enforced across queries, updates, deletes, and IDOR vectors.
"""
from decimal import Decimal
import pytest
from rest_framework import status
from apps.students.models import Student
from apps.academics.models import AcademicYear
from apps.finance.models import Invoice
from tests.conftest import get_auth_client


def test_cross_tenant_header_spoofing_rejected(tenant_a, tenant_b, tenant_a_admin):
    """
    Test that an authenticated user cannot access Tenant B by simply spoofing the X-Tenant-ID header.
    Must return 403 Forbidden.
    """
    client = get_auth_client(tenant_a_admin, tenant=tenant_b)
    response = client.get("/api/v1/students/")

    assert response.status_code == status.HTTP_403_FORBIDDEN
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "CROSS_TENANT_FORBIDDEN"


def test_cross_tenant_student_list_isolation(tenant_a, tenant_b, tenant_a_admin, tenant_b_admin):
    """
    Test that listing students in Tenant A returns ONLY Tenant A students, never Tenant B students.
    """
    # Create student in Tenant A
    student_a = Student.objects.create(
        tenant=tenant_a,
        admission_number="OAK-001",
        first_name="Harry",
        last_name="Potter",
        date_of_birth="2010-07-31",
        gender="M",
        admission_date="2026-01-10",
        status=Student.STATUS_ENROLLED,
    )

    # Create student in Tenant B
    student_b = Student.objects.create(
        tenant=tenant_b,
        admission_number="APX-001",
        first_name="Hermione",
        last_name="Granger",
        date_of_birth="2010-09-19",
        gender="F",
        admission_date="2026-01-10",
        status=Student.STATUS_ENROLLED,
    )

    client_a = get_auth_client(tenant_a_admin, tenant=tenant_a)
    response_a = client_a.get("/api/v1/students/")
    assert response_a.status_code == status.HTTP_200_OK
    results_a = response_a.json()["data"]
    ids_a = [s["id"] for s in results_a]
    assert str(student_a.id) in ids_a
    assert str(student_b.id) not in ids_a

    # Verify Tenant B view
    client_b = get_auth_client(tenant_b_admin, tenant=tenant_b)
    response_b = client_b.get("/api/v1/students/")
    assert response_b.status_code == status.HTTP_200_OK
    results_b = response_b.json()["data"]
    ids_b = [s["id"] for s in results_b]
    assert str(student_b.id) in ids_b
    assert str(student_a.id) not in ids_b


def test_cross_tenant_student_detail_idor_prevention(tenant_a, tenant_b, tenant_a_admin):
    """
    IDOR test: Tenant A admin tries to directly fetch Tenant B student by UUID.
    Must return 404 Not Found.
    """
    student_b = Student.objects.create(
        tenant=tenant_b,
        admission_number="APX-002",
        first_name="Ronald",
        last_name="Weasley",
        date_of_birth="2010-03-01",
        gender="M",
        admission_date="2026-01-10",
    )

    client_a = get_auth_client(tenant_a_admin, tenant=tenant_a)
    response = client_a.get(f"/api/v1/students/{student_b.id}/")

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_cross_tenant_update_prevented(tenant_a, tenant_b, tenant_a_admin):
    """
    Test that Tenant A admin cannot update a Tenant B student record.
    Must return 404 Not Found.
    """
    student_b = Student.objects.create(
        tenant=tenant_b,
        admission_number="APX-003",
        first_name="Draco",
        last_name="Malfoy",
        date_of_birth="2010-06-05",
        gender="M",
        admission_date="2026-01-10",
    )

    client_a = get_auth_client(tenant_a_admin, tenant=tenant_a)
    response = client_a.patch(
        f"/api/v1/students/{student_b.id}/",
        {"first_name": "HackedName"},
        format="json",
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    student_b.refresh_from_db()
    assert student_b.first_name == "Draco"


def test_cross_tenant_delete_prevented(tenant_a, tenant_b, tenant_a_admin):
    """
    Test that Tenant A admin cannot delete a Tenant B student record.
    Must return 404 Not Found.
    """
    student_b = Student.objects.create(
        tenant=tenant_b,
        admission_number="APX-004",
        first_name="Neville",
        last_name="Longbottom",
        date_of_birth="2010-07-30",
        gender="M",
        admission_date="2026-01-10",
    )

    client_a = get_auth_client(tenant_a_admin, tenant=tenant_a)
    response = client_a.delete(f"/api/v1/students/{student_b.id}/")

    assert response.status_code == status.HTTP_404_NOT_FOUND
    student_b.refresh_from_db()
    assert student_b.is_deleted is False


def test_cross_tenant_finance_isolation(tenant_a, tenant_b, tenant_a_admin):
    """
    Test that financial invoices from Tenant B are completely invisible to Tenant A.
    """
    student_b = Student.objects.create(
        tenant=tenant_b,
        admission_number="APX-005",
        first_name="Luna",
        last_name="Lovegood",
        date_of_birth="2011-02-13",
        gender="F",
        admission_date="2026-01-10",
    )
    invoice_b = Invoice.objects.create(
        tenant=tenant_b,
        invoice_number="INV-B-001",
        student=student_b,
        total_amount=Decimal("1500.00"),
        balance_amount=Decimal("1500.00"),
        status=Invoice.STATUS_ISSUED,
        due_date="2026-06-30",
    )

    client_a = get_auth_client(tenant_a_admin, tenant=tenant_a)
    # List invoices
    response_list = client_a.get("/api/v1/finance/invoices/")
    assert response_list.status_code == status.HTTP_200_OK
    assert response_list.json()["meta"]["count"] == 0

    # Direct retrieval by ID
    response_detail = client_a.get(f"/api/v1/finance/invoices/{invoice_b.id}/")
    assert response_detail.status_code == status.HTTP_404_NOT_FOUND
