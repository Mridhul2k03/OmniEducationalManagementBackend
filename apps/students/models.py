"""
Student / Learner domain models. Strictly tenant-scoped.
"""
from django.db import models
from apps.common.models import TenantScopedModel, UUIDModel, TimeStampedModel


class Student(TenantScopedModel):
    STATUS_APPLIED = "applied"
    STATUS_ADMITTED = "admitted"
    STATUS_ENROLLED = "enrolled"
    STATUS_SUSPENDED = "suspended"
    STATUS_GRADUATED = "graduated"
    STATUS_WITHDRAWN = "withdrawn"

    STATUS_CHOICES = (
        (STATUS_APPLIED, "Applied"),
        (STATUS_ADMITTED, "Admitted"),
        (STATUS_ENROLLED, "Enrolled"),
        (STATUS_SUSPENDED, "Suspended"),
        (STATUS_GRADUATED, "Graduated"),
        (STATUS_WITHDRAWN, "Withdrawn"),
    )

    GENDER_MALE = "M"
    GENDER_FEMALE = "F"
    GENDER_OTHER = "O"

    GENDER_CHOICES = (
        (GENDER_MALE, "Male"),
        (GENDER_FEMALE, "Female"),
        (GENDER_OTHER, "Other"),
    )

    admission_number = models.CharField(max_length=50, db_index=True)
    user = models.OneToOneField(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="student_profile",
    )
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)
    blood_group = models.CharField(max_length=10, blank=True, default="")
    admission_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ADMITTED, db_index=True)

    emergency_contact = models.JSONField(default=dict, blank=True)
    # Medical notes are sensitive and restricted
    medical_notes = models.TextField(blank=True, default="")

    class Meta:
        db_table = "students"
        ordering = ["admission_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "admission_number"],
                name="unique_tenant_student_admission_no",
            )
        ]
        indexes = [
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["first_name", "last_name"]),
        ]

    def __str__(self):
        return f"{self.admission_number} - {self.first_name} {self.last_name}"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"


class StudentRegistrationRequest(UUIDModel, TimeStampedModel):
    """
    Tracks learner self-registration and administrative verification requests.
    Supports administrative approval, standard rejection with configurable cooldown,
    and permanent rejection for false/fraudulent requests.
    """
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_PERMANENTLY_REJECTED = "permanently_rejected"

    STATUS_CHOICES = (
        (STATUS_PENDING, "Pending Review"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
        (STATUS_PERMANENTLY_REJECTED, "Permanently Rejected"),
    )

    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="student_registration_requests",
        db_index=True,
    )
    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="student_registration_requests",
    )
    email = models.EmailField(db_index=True)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    phone_number = models.CharField(max_length=50, blank=True, default="")
    admission_number = models.CharField(max_length=50, db_index=True)
    grade_or_program = models.CharField(max_length=150, blank=True, default="")
    gender = models.CharField(max_length=10, choices=Student.GENDER_CHOICES, default=Student.GENDER_FEMALE)
    date_of_birth = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True, default="")

    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
    )

    # Re-request & cooldown tracking
    last_requested_at = models.DateTimeField(auto_now_add=True)
    re_request_count = models.PositiveIntegerField(default=0)

    # Admin review tracking
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_student_requests",
    )
    rejection_reason = models.TextField(blank=True, default="")

    class Meta:
        db_table = "student_registration_requests"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["email", "tenant"]),
            models.Index(fields=["admission_number", "tenant"]),
        ]

    def __str__(self):
        return f"{self.email} ({self.admission_number}) - {self.status}"

    @property
    def applicant_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def can_re_request(self, gap_hours=None):
        """
        Calculates if the student can submit a re-request based on cooldown gap.
        Returns: (is_eligible: bool, time_remaining: timedelta, message: str)
        """
        if gap_hours is None:
            from django.conf import settings
            gap_hours = getattr(settings, "STUDENT_REGISTRATION_REREQUEST_GAP_HOURS", 24)

        if self.status == self.STATUS_PERMANENTLY_REJECTED:
            return False, None, "Registration request has been permanently rejected by the institution administration."
        if self.status == self.STATUS_APPROVED:
            return False, None, "Account has already been verified and approved."

        from django.utils import timezone
        from datetime import timedelta
        now = timezone.now()
        cooldown = timedelta(hours=gap_hours)
        eligible_at = self.last_requested_at + cooldown
        if now >= eligible_at:
            return True, timedelta(0), None

        remaining = eligible_at - now
        return False, remaining, f"You may submit a re-request after the cooldown period ({gap_hours} hours)."

