"""
Student Admission and Management Domain Services.
"""
import uuid
from django.db import transaction
from rest_framework.exceptions import ValidationError
from apps.students.models import Student
from apps.guardians.models import Guardian, StudentGuardian
from apps.enrollments.models import Enrollment
from apps.audit.services import log_audit_event


def admit_student_service(
    tenant,
    student_data: dict,
    guardian_data: dict = None,
    enrollment_data: dict = None,
    actor=None,
    request=None,
) -> Student:
    """
    Executes the multi-step student admission business workflow transactionally:
    1. Validates duplicate records (admission number or name + DOB).
    2. Creates student profile.
    3. If guardian information provided, links guardian.
    4. If enrollment details provided, establishes academic enrollment.
    5. Logs compliance audit trail.
    """
    admission_number = student_data.get("admission_number")
    first_name = student_data.get("first_name", "").strip()
    last_name = student_data.get("last_name", "").strip()
    dob = student_data.get("date_of_birth")

    # 1. Duplicate check: Admission number unique per tenant
    if admission_number and Student.objects.filter(tenant=tenant, admission_number=admission_number).exists():
        raise ValidationError({"admission_number": f"A student with admission number '{admission_number}' already exists in this institution."})

    # Duplicate check: First name + Last name + DOB in same tenant
    if dob and Student.objects.filter(tenant=tenant, first_name__iexact=first_name, last_name__iexact=last_name, date_of_birth=dob).exists():
        raise ValidationError({"non_field_errors": [f"A potential duplicate student record for '{first_name} {last_name}' born on {dob} already exists."]})

    if not admission_number:
        # Auto-generate admission number if not explicitly specified
        count = Student.objects.filter(tenant=tenant).count() + 1
        admission_number = f"ADM-{count:05d}"
        student_data["admission_number"] = admission_number

    with transaction.atomic():
        student = Student.objects.create(
            tenant=tenant,
            created_by=actor,
            **student_data,
        )

        # Link Guardian if provided
        if guardian_data:
            phone = guardian_data.get("phone_number")
            guardian = Guardian.objects.filter(tenant=tenant, phone_number=phone).first()
            if not guardian:
                guardian = Guardian.objects.create(
                    tenant=tenant,
                    created_by=actor,
                    first_name=guardian_data.get("first_name", ""),
                    last_name=guardian_data.get("last_name", ""),
                    phone_number=phone,
                    email=guardian_data.get("email", ""),
                    occupation=guardian_data.get("occupation", ""),
                )

            relationship = guardian_data.get("relationship", StudentGuardian.REL_LEGAL_GUARDIAN)
            StudentGuardian.objects.create(
                tenant=tenant,
                student=student,
                guardian=guardian,
                relationship=relationship,
                is_primary=guardian_data.get("is_primary", True),
                is_emergency_contact=guardian_data.get("is_emergency_contact", True),
                created_by=actor,
            )

        # Enroll into Class/Section if provided
        if enrollment_data:
            Enrollment.objects.create(
                tenant=tenant,
                student=student,
                academic_year_id=enrollment_data.get("academic_year_id"),
                class_cohort_id=enrollment_data.get("class_cohort_id"),
                section_id=enrollment_data.get("section_id"),
                roll_number=enrollment_data.get("roll_number", ""),
                status=Enrollment.STATUS_ACTIVE,
                created_by=actor,
            )
            student.status = Student.STATUS_ENROLLED
            student.save(update_fields=["status"])

        # Record Audit Event
        log_audit_event(
            action="CREATE",
            resource_type="Student",
            resource_id=str(student.id),
            tenant=tenant,
            actor=actor,
            description=f"Student admission completed: {student.full_name} ({student.admission_number}).",
            request=request,
        )

        return student
