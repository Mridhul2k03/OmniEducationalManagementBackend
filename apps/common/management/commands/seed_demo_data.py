"""
Django management command to seed comprehensive demonstration data for OmniEducationalManagement.
Initializes default permissions, tenants, roles, users, classes, students, staff, attendance, and finance.
"""
from datetime import date, timedelta
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import (
    User,
    Membership,
    Role,
    Permission,
    RolePermission,
    MembershipRole,
)
from apps.accounts.serializers import DEFAULT_PERMISSION_DEFINITIONS
from apps.tenants.models import Tenant
from apps.academics.models import (
    AcademicYear,
    Term,
    Department,
    Course,
    Subject,
    ClassCohort,
    Section,
)
from apps.staff.models import Staff
from apps.students.models import Student
from apps.guardians.models import Guardian, StudentGuardian
from apps.enrollments.models import Enrollment
from apps.attendance.models import AttendanceRecord
from apps.examinations.models import Exam, ExamSubject, Mark, GradeScale
from apps.finance.models import FeeCategory, FeeStructure, Invoice, InvoiceLine, Payment
from apps.communications.models import Announcement


class Command(BaseCommand):
    help = "Seeds standard demo data for multi-tenant educational platform."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Beginning OmniEducationalManagement seeding..."))

        with transaction.atomic():
            # 1. Standard Permissions Catalog
            self.stdout.write("Seeding permissions catalog...")
            permissions = {}
            for code, name, module in DEFAULT_PERMISSION_DEFINITIONS:
                perm, _ = Permission.objects.get_or_create(
                    code=code,
                    defaults={"name": name, "module": module, "description": f"Enables {name.lower()}"},
                )
                permissions[code] = perm

            # 2. Superadmin Account
            superadmin, created = User.objects.get_or_create(
                email="superadmin@omniplatform.com",
                defaults={
                    "first_name": "Platform",
                    "last_name": "SuperAdmin",
                    "is_staff": True,
                    "is_superuser": True,
                },
            )
            if created:
                superadmin.set_password("SuperAdminPassword123!")
                superadmin.save()

            # 3. Tenants
            self.stdout.write("Seeding tenants...")
            tenants_data = [
                {
                    "name": "Oxford Crest University",
                    "slug": "oxford-crest",
                    "institution_type": Tenant.TYPE_UNIVERSITY,
                    "contact_email": "admin@oxford-crest.edu",
                    "currency": "USD",
                    "timezone": "America/New_York",
                },
                {
                    "name": "Horizon International STEM School",
                    "slug": "horizon-stem",
                    "institution_type": Tenant.TYPE_SCHOOL,
                    "contact_email": "info@horizon-stem.org",
                    "currency": "EUR",
                    "timezone": "Europe/Berlin",
                },
                {
                    "name": "Apex Elite Prep & Coaching",
                    "slug": "apex-coaching",
                    "institution_type": Tenant.TYPE_COACHING,
                    "contact_email": "contact@apex-coaching.edu",
                    "currency": "INR",
                    "timezone": "Asia/Kolkata",
                },
            ]

            tenants = {}
            for t_info in tenants_data:
                slug = t_info["slug"]
                t, _ = Tenant.objects.get_or_create(
                    slug=slug,
                    defaults={
                        "name": t_info["name"],
                        "institution_type": t_info["institution_type"],
                        "status": Tenant.STATUS_ACTIVE,
                        "contact_email": t_info["contact_email"],
                        "currency": t_info["currency"],
                        "timezone": t_info["timezone"],
                    },
                )
                tenants[slug] = t

            primary_tenant = tenants["oxford-crest"]

            # 4. Roles for primary tenant
            self.stdout.write("Seeding roles for primary tenant...")
            role_admin, _ = Role.objects.get_or_create(
                tenant=primary_tenant,
                code="institute_admin",
                defaults={"name": "Institution Administrator", "is_system_role": True},
            )
            for p in permissions.values():
                RolePermission.objects.get_or_create(role=role_admin, permission=p)

            role_faculty, _ = Role.objects.get_or_create(
                tenant=primary_tenant,
                code="faculty",
                defaults={"name": "Faculty / Instructor", "is_system_role": True},
            )
            for code in ["attendance.mark", "attendance.view", "marks.enter", "marks.review", "students.view"]:
                if code in permissions:
                    RolePermission.objects.get_or_create(role=role_faculty, permission=permissions[code])

            role_student, _ = Role.objects.get_or_create(
                tenant=primary_tenant,
                code="student",
                defaults={"name": "Student", "is_system_role": True},
            )
            for code in ["attendance.view", "fees.view", "students.view"]:
                if code in permissions:
                    RolePermission.objects.get_or_create(role=role_student, permission=permissions[code])

            role_accountant, _ = Role.objects.get_or_create(
                tenant=primary_tenant,
                code="accountant",
                defaults={"name": "Accountant / Bursar", "is_system_role": True},
            )
            for code in ["fees.view", "fees.create_invoice", "fees.record_payment", "fees.refund", "students.view"]:
                if code in permissions:
                    RolePermission.objects.get_or_create(role=role_accountant, permission=permissions[code])

            # 5. Seed Users & Memberships
            self.stdout.write("Seeding demo users...")
            demo_users_data = [
                {
                    "email": "eleanor.vance@omni-edu.org",
                    "first_name": "Eleanor",
                    "last_name": "Vance",
                    "role": role_admin,
                },
                {
                    "email": "arthur.pendelton@omni-edu.org",
                    "first_name": "Arthur",
                    "last_name": "Pendelton",
                    "role": role_faculty,
                },
                {
                    "email": "sophia.martinez@student.omni-edu.org",
                    "first_name": "Sophia",
                    "last_name": "Martinez",
                    "role": role_student,
                },
                {
                    "email": "marcus.sterling@omni-edu.org",
                    "first_name": "Marcus",
                    "last_name": "Sterling",
                    "role": role_accountant,
                },
            ]

            created_users = {}
            for u_data in demo_users_data:
                user, u_created = User.objects.get_or_create(
                    email=u_data["email"],
                    defaults={
                        "first_name": u_data["first_name"],
                        "last_name": u_data["last_name"],
                        "is_active": True,
                    },
                )
                user.set_password("Password123!")
                user.save()
                created_users[u_data["email"]] = user

                # Create membership across all tenants, default to oxford-crest
                for t_slug, tenant_obj in tenants.items():
                    m, _ = Membership.objects.get_or_create(
                        user=user,
                        tenant=tenant_obj,
                        defaults={
                            "status": Membership.STATUS_ACTIVE,
                            "is_default": (t_slug == "oxford-crest"),
                        },
                    )
                    MembershipRole.objects.get_or_create(membership=m, role=u_data["role"])

            # 6. Academic Setup
            self.stdout.write("Seeding academic structure...")
            acad_year, _ = AcademicYear.objects.get_or_create(
                tenant=primary_tenant,
                name="2026-2027",
                defaults={
                    "start_date": date(2026, 8, 1),
                    "end_date": date(2027, 6, 30),
                    "is_current": True,
                },
            )

            term, _ = Term.objects.get_or_create(
                tenant=primary_tenant,
                academic_year=acad_year,
                name="Fall 2026",
                defaults={
                    "start_date": date(2026, 8, 1),
                    "end_date": date(2026, 12, 20),
                    "is_current": True,
                },
            )

            dept_cs, _ = Department.objects.get_or_create(
                tenant=primary_tenant,
                name="Computer Science & Engineering",
                defaults={"code": "CSE"},
            )

            course_bsc, _ = Course.objects.get_or_create(
                tenant=primary_tenant,
                department=dept_cs,
                name="B.S. Computer Science",
                defaults={"code": "BSC-CS"},
            )

            subj_algo, _ = Subject.objects.get_or_create(
                tenant=primary_tenant,
                department=dept_cs,
                code="CS-304",
                defaults={"name": "Advanced Algorithms & Data Structures", "subject_type": Subject.TYPE_THEORY},
            )
            subj_db, _ = Subject.objects.get_or_create(
                tenant=primary_tenant,
                department=dept_cs,
                code="CS-301",
                defaults={"name": "Relational Database Systems", "subject_type": Subject.TYPE_THEORY},
            )

            cohort_cs, _ = ClassCohort.objects.get_or_create(
                tenant=primary_tenant,
                academic_year=acad_year,
                name="Year 3 Computer Science",
                defaults={"course": course_bsc},
            )

            section_a, _ = Section.objects.get_or_create(
                tenant=primary_tenant,
                class_cohort=cohort_cs,
                name="Section A",
                defaults={"capacity": 40},
            )

            # 7. Staff / Faculty Member
            self.stdout.write("Seeding staff profile...")
            faculty_user = created_users["arthur.pendelton@omni-edu.org"]
            Staff.objects.get_or_create(
                tenant=primary_tenant,
                user=faculty_user,
                defaults={
                    "employee_id": "EMP-2024-042",
                    "department": dept_cs,
                    "designation": "Associate Professor",
                    "qualification": "Ph.D. Computer Science",
                    "joined_date": date(2022, 8, 15),
                    "employment_type": Staff.TYPE_FULL_TIME,
                    "status": Staff.STATUS_ACTIVE,
                },
            )

            # 8. Students, Guardians & Enrollments
            self.stdout.write("Seeding students and enrollments...")
            students_catalog = [
                ("ADM-2024-001", "Sophia", "Martinez", "F", "A+", "2004-04-12", True),
                ("ADM-2024-002", "Liam", "Chen", "M", "B+", "2004-07-23", False),
                ("ADM-2024-003", "Amara", "Okafor", "F", "O+", "2004-09-14", False),
                ("ADM-2024-004", "Lucas", "Dubois", "M", "AB+", "2004-11-05", False),
                ("ADM-2024-005", "Zara", "Al-Mansoor", "F", "B-", "2005-01-19", False),
                ("ADM-2024-006", "Ethan", "Hawkins", "M", "O-", "2004-03-30", False),
            ]

            seeded_students = []
            for idx, (adm_no, fn, ln, g, bg, dob_str, is_linked_user) in enumerate(students_catalog):
                u = created_users["sophia.martinez@student.omni-edu.org"] if is_linked_user else None
                student, _ = Student.objects.get_or_create(
                    tenant=primary_tenant,
                    admission_number=adm_no,
                    defaults={
                        "user": u,
                        "first_name": fn,
                        "last_name": ln,
                        "date_of_birth": date.fromisoformat(dob_str),
                        "gender": g,
                        "blood_group": bg,
                        "admission_date": date(2024, 8, 20),
                        "status": Student.STATUS_ENROLLED,
                        "emergency_contact": "+15550192834",
                    },
                )
                seeded_students.append(student)

                # Link Guardian
                guardian, _ = Guardian.objects.get_or_create(
                    tenant=primary_tenant,
                    email=f"guardian.{adm_no.lower()}@family.org",
                    defaults={
                        "first_name": f"ParentOf{fn}",
                        "last_name": ln,
                        "phone_number": "+15558473921",
                    },
                )
                StudentGuardian.objects.get_or_create(
                    tenant=primary_tenant,
                    student=student,
                    guardian=guardian,
                    defaults={"relationship": StudentGuardian.REL_LEGAL_GUARDIAN, "is_primary": True},
                )

                # Enrollment
                Enrollment.objects.get_or_create(
                    tenant=primary_tenant,
                    student=student,
                    academic_year=acad_year,
                    defaults={
                        "class_cohort": cohort_cs,
                        "section": section_a,
                        "roll_number": f"CS3-A-{idx+1:02d}",
                        "status": Enrollment.STATUS_ACTIVE,
                    },
                )

            # 9. Attendance records
            self.stdout.write("Seeding attendance records...")
            today = date.today()
            yesterday = today - timedelta(days=1)
            statuses = ["present", "present", "late", "present", "present", "absent"]
            for st, student in zip(statuses, seeded_students):
                AttendanceRecord.objects.get_or_create(
                    tenant=primary_tenant,
                    student=student,
                    date=yesterday,
                    defaults={
                        "status": st,
                        "section": section_a,
                        "subject": subj_algo,
                        "marked_by": created_users["arthur.pendelton@omni-edu.org"],
                        "remarks": "Traffic delay" if st == "late" else ("Medical note" if st == "absent" else ""),
                    },
                )

            # 10. Grade Scales, Exams & Marks
            self.stdout.write("Seeding exams and marks...")
            grade_scale, _ = GradeScale.objects.get_or_create(
                tenant=primary_tenant,
                name="University 4.0 Scale",
                defaults={
                    "description": "Standard 4.0 Scale with letter grades",
                    "rules": [
                        {"grade": "A+", "min_percent": 93, "max_percent": 100, "grade_point": 4.0},
                        {"grade": "A", "min_percent": 85, "max_percent": 92.99, "grade_point": 3.8},
                        {"grade": "B+", "min_percent": 75, "max_percent": 84.99, "grade_point": 3.3},
                        {"grade": "B", "min_percent": 65, "max_percent": 74.99, "grade_point": 3.0},
                        {"grade": "C", "min_percent": 50, "max_percent": 64.99, "grade_point": 2.0},
                        {"grade": "F", "min_percent": 0, "max_percent": 49.99, "grade_point": 0.0},
                    ],
                },
            )

            midterm_exam, _ = Exam.objects.get_or_create(
                tenant=primary_tenant,
                name="Midterm Examination Fall 2026",
                defaults={
                    "academic_year": acad_year,
                    "term": term,
                    "class_cohort": cohort_cs,
                    "exam_type": "midterm",
                    "start_date": date(2026, 10, 10),
                    "end_date": date(2026, 10, 18),
                    "status": Exam.STATUS_SCHEDULED,
                    "is_published": False,
                },
            )

            exam_subj, _ = ExamSubject.objects.get_or_create(
                tenant=primary_tenant,
                exam=midterm_exam,
                subject=subj_algo,
                defaults={
                    "exam_date": date(2026, 10, 12),
                    "start_time": "09:00:00",
                    "end_time": "12:00:00",
                    "max_marks": Decimal("100.00"),
                    "passing_marks": Decimal("40.00"),
                },
            )

            sample_scores = [Decimal("94.5"), Decimal("88.0"), Decimal("78.5"), Decimal("91.0"), Decimal("84.0"), Decimal("68.5")]
            for score, student in zip(sample_scores, seeded_students):
                Mark.objects.get_or_create(
                    tenant=primary_tenant,
                    exam_subject=exam_subj,
                    student=student,
                    defaults={
                        "marks_obtained": score,
                        "status": Mark.STATUS_APPROVED,
                        "remarks": "Excellent work" if score >= 85 else "Good performance",
                        "is_absent": False,
                        "entered_by": created_users["arthur.pendelton@omni-edu.org"],
                    },
                )

            # 11. Finance: Categories, Fee Structures, Invoices & Payments
            self.stdout.write("Seeding finance structures and invoices...")
            fee_cat, _ = FeeCategory.objects.get_or_create(
                tenant=primary_tenant,
                name="Tuition Fee",
                defaults={"description": "Semester Tuition"},
            )

            fee_struct, _ = FeeStructure.objects.get_or_create(
                tenant=primary_tenant,
                academic_year=acad_year,
                class_cohort=cohort_cs,
                category=fee_cat,
                name="B.Sc. Tuition Fee 2026",
                defaults={
                    "amount": Decimal("4500.00"),
                    "due_date": date(2026, 9, 30),
                },
            )

            # Create invoices for first two students
            inv_1, _ = Invoice.objects.get_or_create(
                tenant=primary_tenant,
                invoice_number="INV-2026-0001",
                defaults={
                    "student": seeded_students[0],
                    "total_amount": Decimal("4500.00"),
                    "discount_amount": Decimal("0.00"),
                    "paid_amount": Decimal("4500.00"),
                    "balance_amount": Decimal("0.00"),
                    "due_date": date(2026, 9, 30),
                    "status": Invoice.STATUS_PAID,
                },
            )
            InvoiceLine.objects.get_or_create(
                tenant=primary_tenant,
                invoice=inv_1,
                defaults={"fee_structure": fee_struct, "description": "Semester Tuition Fall 2026", "amount": Decimal("4500.00")},
            )
            Payment.objects.get_or_create(
                tenant=primary_tenant,
                invoice=inv_1,
                receipt_number="RCP-2026-001",
                defaults={
                    "amount": Decimal("4500.00"),
                    "payment_method": Payment.METHOD_CARD,
                    "transaction_reference": "TXN-CRD-8392",
                    "status": Payment.STATUS_SUCCESS,
                },
            )

            inv_2, _ = Invoice.objects.get_or_create(
                tenant=primary_tenant,
                invoice_number="INV-2026-0002",
                defaults={
                    "student": seeded_students[1],
                    "total_amount": Decimal("4500.00"),
                    "discount_amount": Decimal("0.00"),
                    "paid_amount": Decimal("2250.00"),
                    "balance_amount": Decimal("2250.00"),
                    "due_date": date(2026, 9, 30),
                    "status": Invoice.STATUS_PARTIALLY_PAID,
                },
            )
            InvoiceLine.objects.get_or_create(
                tenant=primary_tenant,
                invoice=inv_2,
                defaults={"fee_structure": fee_struct, "description": "Semester Tuition Fall 2026 (Installment 1)", "amount": Decimal("4500.00")},
            )
            Payment.objects.get_or_create(
                tenant=primary_tenant,
                invoice=inv_2,
                receipt_number="RCP-2026-002",
                defaults={
                    "amount": Decimal("2250.00"),
                    "payment_method": Payment.METHOD_BANK,
                    "transaction_reference": "TXN-BNK-9921",
                    "status": Payment.STATUS_SUCCESS,
                },
            )

            # 12. Communications: Announcements
            self.stdout.write("Seeding announcements...")
            Announcement.objects.get_or_create(
                tenant=primary_tenant,
                title="Fall 2026 Semester Portal Launch",
                defaults={
                    "content": "Welcome to the unified OMNI Educational SaaS Platform. All student and faculty services are now live.",
                    "target_audience": Announcement.AUDIENCE_ALL,
                    "is_published": True,
                },
            )
            Announcement.objects.get_or_create(
                tenant=primary_tenant,
                title="Midterm Examination Schedule Released",
                defaults={
                    "content": "The midterm examination timetable has been published. Please review schedules in your dashboard.",
                    "target_audience": Announcement.AUDIENCE_STUDENTS,
                    "is_published": True,
                },
            )

        self.stdout.write(self.style.SUCCESS("OmniEducationalManagement seed data successfully created!"))
