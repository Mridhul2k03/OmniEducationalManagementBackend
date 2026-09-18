"""
Student / Learner domain models. Strictly tenant-scoped.
"""
from django.db import models
from apps.common.models import TenantScopedModel


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
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)
    blood_group = models.CharField(max_length=10, blank=True, default="")
    admission_date = models.DateField()
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
