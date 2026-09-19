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
    if not tenant:
        raise ValidationError({"tenant": "An active educational institution / tenant is required to admit a student."})

    admission_number = student_data.get("admission_number")
    first_name = student_data.get("first_name", "").strip()
    last_name = student_data.get("last_name", "").strip()
    dob = student_data.get("date_of_birth")

    from datetime import date

    # 1. Duplicate check: Admission number unique per tenant (including soft-deleted records)
    if admission_number and Student.all_objects.filter(tenant=tenant, admission_number=admission_number).exists():
        raise ValidationError({"admission_number": f"A student with admission number '{admission_number}' already exists in this institution."})

    # Duplicate check: First name + Last name + DOB in same tenant
    if dob and Student.objects.filter(tenant=tenant, first_name__iexact=first_name, last_name__iexact=last_name, date_of_birth=dob).exists():
        raise ValidationError({"non_field_errors": [f"A potential duplicate student record for '{first_name} {last_name}' born on {dob} already exists."]})

    if not admission_number:
        # Auto-generate collision-free admission number
        year = date.today().year
        total = Student.all_objects.filter(tenant=tenant).count() + 1
        admission_number = f"ADM-{year}-{total:04d}"
        seq = total
        while Student.all_objects.filter(tenant=tenant, admission_number=admission_number).exists():
            seq += 1
            admission_number = f"ADM-{year}-{seq:04d}"
        student_data["admission_number"] = admission_number

    with transaction.atomic():
        # 1. Create Student profile
        email = student_data.pop("email", None)
        student = Student.objects.create(
            tenant=tenant,
            created_by=actor,
            **student_data,
        )

        # 2. Create User Account & Tenant Membership
        from apps.accounts.models import User, Membership, Role, MembershipRole
        from apps.academics.models import AcademicYear, ClassCohort, Section
        from apps.finance.models import FeeStructure, Invoice, InvoiceLine
        from apps.communications.models import Notification
        from datetime import timedelta

        clean_fn = first_name.lower().replace(" ", "")
        clean_ln = last_name.lower().replace(" ", "")
        adm_clean = student.admission_number.lower().replace("-", "")
        student_email = email or f"{clean_fn}.{clean_ln}.{adm_clean}@{tenant.slug}.omni-edu.org"

        user, user_created = User.objects.get_or_create(
            email=student_email,
            defaults={
                "first_name": first_name,
                "last_name": last_name,
                "is_active": True,
            },
        )
        if user_created:
            user.set_password("Student123!")
            user.save()

        student.user = user
        student.save(update_fields=["user"])

        # Assign Student Role and Tenant Membership
        student_role = Role.objects.filter(code="student").first()
        membership, _ = Membership.objects.get_or_create(
            tenant=tenant,
            user=user,
            defaults={
                "status": Membership.STATUS_ACTIVE,
                "is_default": True,
            },
        )
        if student_role:
            MembershipRole.objects.get_or_create(
                membership=membership,
                role=student_role,
            )

        # 3. Link Guardian if provided
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

        # 4. Academic Enrollment (explicit or auto-enroll into tenant's current structure)
        ay_id = enrollment_data.get("academic_year_id") if enrollment_data else None
        cc_id = enrollment_data.get("class_cohort_id") if enrollment_data else None
        sec_id = enrollment_data.get("section_id") if enrollment_data else None
        c_name = enrollment_data.get("class_name", "") if enrollment_data else ""
        roll_num = enrollment_data.get("roll_number", "") if enrollment_data else ""

        academic_year = None
        if ay_id:
            academic_year = AcademicYear.objects.filter(tenant=tenant, id=ay_id).first()
        if not academic_year:
            academic_year = AcademicYear.objects.filter(tenant=tenant).order_by("-is_current", "-start_date").first()

        class_cohort = None
        if cc_id:
            class_cohort = ClassCohort.objects.filter(tenant=tenant, id=cc_id).first()
        elif c_name:
            class_cohort = ClassCohort.objects.filter(tenant=tenant, name__icontains=c_name).first()
        if not class_cohort and academic_year:
            class_cohort = ClassCohort.objects.filter(tenant=tenant, academic_year=academic_year).first()
        if not class_cohort:
            class_cohort = ClassCohort.objects.filter(tenant=tenant).first()

        section = None
        if sec_id:
            section = Section.objects.filter(tenant=tenant, id=sec_id).first()
        if not section and class_cohort:
            section = Section.objects.filter(tenant=tenant, class_cohort=class_cohort).first()
            if not section:
                section = Section.objects.create(
                    tenant=tenant,
                    class_cohort=class_cohort,
                    name="Section A",
                    created_by=actor,
                )

        if academic_year and class_cohort and section:
            if not roll_num:
                r_count = Enrollment.objects.filter(tenant=tenant, academic_year=academic_year, class_cohort=class_cohort).count() + 1
                roll_num = f"R-{r_count:03d}"

            Enrollment.objects.get_or_create(
                tenant=tenant,
                student=student,
                academic_year=academic_year,
                defaults={
                    "class_cohort": class_cohort,
                    "section": section,
                    "roll_number": roll_num,
                    "status": Enrollment.STATUS_ACTIVE,
                    "created_by": actor,
                },
            )
            student.status = Student.STATUS_ENROLLED
            student.save(update_fields=["status"])

        # 5. Finance Billing: Generate Initial Fee Invoice if Fee Structures Exist
        fee_structures = FeeStructure.objects.filter(tenant=tenant)
        if fee_structures.exists():
            due_date = date.today() + timedelta(days=30)
            inv_count = Invoice.objects.filter(tenant=tenant).count() + 1
            inv_number = f"INV-{inv_count:06d}"
            while Invoice.objects.filter(tenant=tenant, invoice_number=inv_number).exists():
                inv_count += 1
                inv_number = f"INV-{inv_count:06d}"

            selected_struct = None
            if class_cohort:
                selected_struct = fee_structures.filter(class_cohort=class_cohort).first()
            if not selected_struct:
                selected_struct = fee_structures.first()

            if selected_struct:
                inv = Invoice.objects.create(
                    tenant=tenant,
                    invoice_number=inv_number,
                    student=student,
                    total_amount=selected_struct.amount,
                    discount_amount=0,
                    paid_amount=0,
                    balance_amount=selected_struct.amount,
                    status=Invoice.STATUS_ISSUED,
                    due_date=due_date,
                    created_by=actor,
                )
                InvoiceLine.objects.create(
                    tenant=tenant,
                    invoice=inv,
                    fee_structure=selected_struct,
                    description=f"Admission & {selected_struct.name}",
                    amount=selected_struct.amount,
                    created_by=actor,
                )

        # 6. Dispatch In-App Welcome Notification
        Notification.objects.create(
            tenant=tenant,
            recipient=user,
            title=f"Welcome to {tenant.name}",
            message=f"Welcome {student.full_name}! Your student admission ({student.admission_number}) has been finalized and enrolled successfully.",
            channel=Notification.CHANNEL_IN_APP,
        )

        # 7. Record Audit Event
        log_audit_event(
            action="CREATE",
            resource_type="Student",
            resource_id=str(student.id),
            tenant=tenant,
            actor=actor,
            description=f"Student admission completed with user credentials, enrollment, invoice, and welcome notification: {student.full_name} ({student.admission_number}).",
            request=request,
        )

        return student
