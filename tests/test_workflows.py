"""
End-to-End Business Workflow Test Suite.
Tests Admissions, Attendance, Examinations & Publication Lock, and Fees & Idempotent Payments.
"""
from decimal import Decimal
import pytest
from rest_framework import status
from apps.academics.models import AcademicYear, ClassCohort, Section, Subject
from apps.students.models import Student
from apps.guardians.models import Guardian, StudentGuardian
from apps.enrollments.models import Enrollment
from apps.attendance.models import AttendanceRecord, AttendanceCorrectionRequest
from apps.examinations.models import Exam, ExamSubject, Mark
from apps.finance.models import FeeCategory, FeeStructure, Invoice, Payment
from tests.conftest import get_auth_client


def test_admission_workflow_and_duplicate_prevention(tenant_a, tenant_a_admin):
    """
    Test End-to-End Admission Workflow:
    - Creates student, guardian, and enrollment record atomically.
    - Tests duplicate rejection.
    """
    client = get_auth_client(tenant_a_admin, tenant=tenant_a)

    # Setup academic context
    year = AcademicYear.objects.create(
        tenant=tenant_a,
        name="2026-2027",
        start_date="2026-06-01",
        end_date="2027-05-31",
        is_current=True,
    )
    cohort = ClassCohort.objects.create(
        tenant=tenant_a,
        academic_year=year,
        name="Grade 10",
    )
    section = Section.objects.create(
        tenant=tenant_a,
        class_cohort=cohort,
        name="A",
    )

    admission_payload = {
        "admission_number": "ADM-2026-001",
        "first_name": "Edward",
        "last_name": "Elric",
        "date_of_birth": "2011-02-03",
        "gender": "M",
        "blood_group": "B+",
        "admission_date": "2026-06-15",
        "guardian": {
            "first_name": "Van",
            "last_name": "Hohenheim",
            "phone_number": "+15551234567",
            "relationship": "father",
            "email": "hohenheim@alchemy.edu",
        },
        "academic_year_id": str(year.id),
        "class_cohort_id": str(cohort.id),
        "section_id": str(section.id),
        "roll_number": "10-A-01",
    }

    # 1. Successful Admission
    response = client.post("/api/v1/students/admit/", admission_payload, format="json")
    assert response.status_code == status.HTTP_201_CREATED

    student_id = response.json()["data"]["id"]
    student = Student.objects.get(id=student_id)
    assert student.status == Student.STATUS_ENROLLED
    assert student.admission_number == "ADM-2026-001"

    # Verify Guardian linkage
    assert student.guardian_links.count() == 1
    link = student.guardian_links.first()
    assert link.guardian.first_name == "Van"
    assert link.relationship == "father"

    # Verify Academic Enrollment
    assert student.enrollments.count() == 1
    enrollment = student.enrollments.first()
    assert enrollment.section == section
    assert enrollment.roll_number == "10-A-01"

    # 2. Duplicate Check: Same admission number must fail
    dup_resp = client.post("/api/v1/students/admit/", admission_payload, format="json")
    assert dup_resp.status_code == status.HTTP_400_BAD_REQUEST


def test_attendance_and_correction_workflow(tenant_a, tenant_a_teacher, tenant_a_admin):
    """
    Test Attendance Workflow:
    - Teacher bulk marks attendance.
    - Correction request created and approved.
    """
    teacher_client = get_auth_client(tenant_a_teacher, tenant=tenant_a)
    admin_client = get_auth_client(tenant_a_admin, tenant=tenant_a)

    year = AcademicYear.objects.create(tenant=tenant_a, name="2026", start_date="2026-01-01", end_date="2026-12-31")
    cohort = ClassCohort.objects.create(tenant=tenant_a, academic_year=year, name="Grade 8")
    section = Section.objects.create(tenant=tenant_a, class_cohort=cohort, name="A")

    student1 = Student.objects.create(tenant=tenant_a, admission_number="S1", first_name="A", last_name="B", date_of_birth="2012-01-01", gender="M", admission_date="2026-01-01")
    student2 = Student.objects.create(tenant=tenant_a, admission_number="S2", first_name="C", last_name="D", date_of_birth="2012-01-01", gender="F", admission_date="2026-01-01")

    Enrollment.objects.create(tenant=tenant_a, student=student1, academic_year=year, class_cohort=cohort, section=section)
    Enrollment.objects.create(tenant=tenant_a, student=student2, academic_year=year, class_cohort=cohort, section=section)

    # 1. Bulk mark attendance
    mark_payload = {
        "section_id": str(section.id),
        "date": "2026-09-18",
        "entries": [
            {"student_id": str(student1.id), "status": AttendanceRecord.STATUS_PRESENT},
            {"student_id": str(student2.id), "status": AttendanceRecord.STATUS_ABSENT, "remarks": "Sick"},
        ],
    }
    resp_mark = teacher_client.post("/api/v1/attendance/records/bulk-mark/", mark_payload, format="json")
    assert resp_mark.status_code == status.HTTP_200_OK

    rec2 = AttendanceRecord.objects.get(student=student2, date="2026-09-18")
    assert rec2.status == AttendanceRecord.STATUS_ABSENT

    # 2. Submit correction request for student2 from ABSENT to EXCUSED
    corr_resp = teacher_client.post(
        "/api/v1/attendance/corrections/",
        {
            "attendance_record": str(rec2.id),
            "requested_status": AttendanceRecord.STATUS_EXCUSED,
            "reason": "Parent provided medical certificate.",
        },
        format="json",
    )
    assert corr_resp.status_code == status.HTTP_201_CREATED
    corr_id = corr_resp.json()["id"]

    # 3. Admin approves correction
    appr_resp = admin_client.post(f"/api/v1/attendance/corrections/{corr_id}/approve/")
    assert appr_resp.status_code == status.HTTP_200_OK

    rec2.refresh_from_db()
    assert rec2.status == AttendanceRecord.STATUS_EXCUSED


def test_examination_publication_lock_workflow(tenant_a, tenant_a_teacher, tenant_a_admin):
    """
    Test Examination Workflow:
    - Exam scheduled.
    - Marks entered and validated.
    - Marks > max_marks rejected.
    - Admin publishes exam.
    - Subsequent edits to marks are blocked (immutable lock).
    """
    teacher_client = get_auth_client(tenant_a_teacher, tenant=tenant_a)
    admin_client = get_auth_client(tenant_a_admin, tenant=tenant_a)

    year = AcademicYear.objects.create(tenant=tenant_a, name="2026", start_date="2026-01-01", end_date="2026-12-31")
    cohort = ClassCohort.objects.create(tenant=tenant_a, academic_year=year, name="Grade 11")
    subject = Subject.objects.create(tenant=tenant_a, name="Physics", code="PHY101")
    student = Student.objects.create(tenant=tenant_a, admission_number="S100", first_name="Isaac", last_name="Newton", date_of_birth="2010-01-04", gender="M", admission_date="2026-01-01")

    exam = Exam.objects.create(
        tenant=tenant_a,
        academic_year=year,
        class_cohort=cohort,
        name="Midterm Physics 2026",
        start_date="2026-10-01",
        end_date="2026-10-10",
        status=Exam.STATUS_SCHEDULED,
    )
    schedule = ExamSubject.objects.create(
        tenant=tenant_a,
        exam=exam,
        subject=subject,
        exam_date="2026-10-02",
        start_time="09:00:00",
        end_time="12:00:00",
        max_marks=Decimal("100.00"),
        passing_marks=Decimal("40.00"),
    )

    # 1. Invalid mark (> max marks) rejected
    resp_invalid = teacher_client.post(
        "/api/v1/exams/marks/",
        {
            "exam_subject": str(schedule.id),
            "student": str(student.id),
            "marks_obtained": "120.00",
        },
        format="json",
    )
    assert resp_invalid.status_code == status.HTTP_400_BAD_REQUEST

    # 2. Valid mark entry
    resp_valid = teacher_client.post(
        "/api/v1/exams/marks/",
        {
            "exam_subject": str(schedule.id),
            "student": str(student.id),
            "marks_obtained": "95.50",
            "remarks": "Excellent score",
        },
        format="json",
    )
    assert resp_valid.status_code == status.HTTP_201_CREATED
    mark_id = resp_valid.json()["id"]

    # 3. Publish Exam Results
    resp_pub = admin_client.post(f"/api/v1/exams/exams/{exam.id}/publish/")
    assert resp_pub.status_code == status.HTTP_200_OK
    exam.refresh_from_db()
    assert exam.is_published is True

    # 4. Attempt to modify mark after publication must be blocked
    resp_edit = teacher_client.patch(
        f"/api/v1/exams/marks/{mark_id}/",
        {"marks_obtained": "98.00"},
        format="json",
    )
    assert resp_edit.status_code == status.HTTP_400_BAD_REQUEST


def test_finance_invoice_and_idempotent_payment_workflow(tenant_a, tenant_a_accountant):
    """
    Test Fees & Payment Workflow:
    - Generate invoice from fee structures.
    - Process payment with idempotency key.
    - Verify duplicate submission with same key does not double-charge.
    - Fully paid invoice updates status to PAID.
    """
    client = get_auth_client(tenant_a_accountant, tenant=tenant_a)

    year = AcademicYear.objects.create(tenant=tenant_a, name="2026", start_date="2026-01-01", end_date="2026-12-31")
    cohort = ClassCohort.objects.create(tenant=tenant_a, academic_year=year, name="Grade 9")
    category = FeeCategory.objects.create(tenant=tenant_a, name="Term 1 Tuition")
    structure = FeeStructure.objects.create(
        tenant=tenant_a,
        academic_year=year,
        class_cohort=cohort,
        category=category,
        name="Tuition Fee Term 1",
        amount=Decimal("1000.00"),
        due_date="2026-10-15",
    )
    student = Student.objects.create(
        tenant=tenant_a,
        admission_number="FEE-001",
        first_name="Oliver",
        last_name="Twist",
        date_of_birth="2012-05-10",
        gender="M",
        admission_date="2026-01-01",
    )

    # 1. Generate Invoice with $100 scholarship/discount
    inv_resp = client.post(
        "/api/v1/finance/invoices/generate/",
        {
            "student_id": str(student.id),
            "fee_structure_ids": [str(structure.id)],
            "due_date": "2026-10-15",
            "discount_amount": "100.00",
        },
        format="json",
    )
    assert inv_resp.status_code == status.HTTP_201_CREATED
    invoice_id = inv_resp.json()["data"]["id"]

    invoice = Invoice.objects.get(id=invoice_id)
    assert invoice.total_amount == Decimal("1000.00")
    assert invoice.discount_amount == Decimal("100.00")
    assert invoice.balance_amount == Decimal("900.00")
    assert invoice.status == Invoice.STATUS_ISSUED

    # 2. Record Payment with Idempotency Key
    idempotency_key = "idemp-pay-test-999"
    pay_payload = {
        "invoice_id": str(invoice.id),
        "amount": "900.00",
        "payment_method": "online",
        "transaction_reference": "TXN-BANK-12345",
        "idempotency_key": idempotency_key,
    }

    pay_resp = client.post("/api/v1/finance/payments/record/", pay_payload, format="json")
    assert pay_resp.status_code == status.HTTP_201_CREATED
    receipt_no = pay_resp.json()["data"]["receipt_number"]

    invoice.refresh_from_db()
    assert invoice.paid_amount == Decimal("900.00")
    assert invoice.balance_amount == Decimal("0.00")
    assert invoice.status == Invoice.STATUS_PAID

    # 3. Repeat submission with SAME idempotency key
    # Must safely return original payment without deducting again or erroring
    dup_pay_resp = client.post("/api/v1/finance/payments/record/", pay_payload, format="json")
    assert dup_pay_resp.status_code == status.HTTP_201_CREATED
    assert dup_pay_resp.json()["data"]["receipt_number"] == receipt_no
    assert Payment.objects.filter(idempotency_key=idempotency_key).count() == 1
