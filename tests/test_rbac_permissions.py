"""
RBAC & Permission Matrix Automated Test Suite.
Verifies role boundaries for Institution Admins, Teachers, Accountants, and Students.
"""
from decimal import Decimal
import pytest
from rest_framework import status
from rest_framework.test import APIClient
from apps.academics.models import AcademicYear, ClassCohort, Section, Subject
from apps.students.models import Student
from apps.examinations.models import Exam, ExamSubject, Mark
from apps.finance.models import FeeCategory, FeeStructure
from tests.conftest import get_auth_client


def test_unauthenticated_access_rejected():
    """
    Test that unauthenticated requests to protected endpoints return 401.
    """
    client = APIClient()
    response = client.get("/api/v1/students/")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "AUTHENTICATION_REQUIRED"


def test_teacher_permission_boundaries(tenant_a, tenant_a_teacher):
    """
    Verify Teacher role boundaries:
    - Teacher CAN view students.
    - Teacher CANNOT create financial invoices (403).
    - Teacher CANNOT publish exam results (403).
    """
    client = get_auth_client(tenant_a_teacher, tenant=tenant_a)

    # 1. View students: Allowed
    resp_students = client.get("/api/v1/students/")
    assert resp_students.status_code == status.HTTP_200_OK

    # 2. Create invoice: Forbidden
    resp_invoice = client.post(
        "/api/v1/finance/invoices/generate/",
        {"student_id": "00000000-0000-0000-0000-000000000000", "fee_structure_ids": [], "due_date": "2026-10-01"},
        format="json",
    )
    assert resp_invoice.status_code == status.HTTP_403_FORBIDDEN

    # 3. Publish exam results: Forbidden
    resp_publish = client.post("/api/v1/exams/exams/00000000-0000-0000-0000-000000000000/publish/")
    assert resp_publish.status_code == status.HTTP_403_FORBIDDEN


def test_accountant_permission_boundaries(tenant_a, tenant_a_accountant):
    """
    Verify Accountant role boundaries:
    - Accountant CAN view fees and structures.
    - Accountant CANNOT mark attendance (403).
    - Accountant CANNOT enter exam marks (403).
    """
    client = get_auth_client(tenant_a_accountant, tenant=tenant_a)

    # 1. View fees: Allowed
    resp_fees = client.get("/api/v1/finance/categories/")
    assert resp_fees.status_code == status.HTTP_200_OK

    # 2. Mark attendance: Forbidden
    resp_att = client.post(
        "/api/v1/attendance/records/bulk-mark/",
        {"section_id": "00000000-0000-0000-0000-000000000000", "date": "2026-09-18", "entries": []},
        format="json",
    )
    assert resp_att.status_code == status.HTTP_403_FORBIDDEN

    # 3. Enter marks: Forbidden
    resp_marks = client.post(
        "/api/v1/exams/marks/",
        {"exam_subject": "00000000-0000-0000-0000-000000000000", "student": "00000000-0000-0000-0000-000000000000", "marks_obtained": 85},
        format="json",
    )
    assert resp_marks.status_code == status.HTTP_403_FORBIDDEN


def test_institution_admin_has_full_tenant_privileges(tenant_a, tenant_a_admin):
    """
    Verify Institution Admin can manage academic setup and view all audit logs.
    """
    client = get_auth_client(tenant_a_admin, tenant=tenant_a)

    # Create academic year
    response = client.post(
        "/api/v1/academics/years/",
        {
            "name": "Academic Year 2026-2027",
            "start_date": "2026-06-01",
            "end_date": "2027-05-31",
            "is_current": True,
        },
        format="json",
    )
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["name"] == "Academic Year 2026-2027"

    # View Audit Logs
    resp_audit = client.get("/api/v1/audit/")
    assert resp_audit.status_code == status.HTTP_200_OK
