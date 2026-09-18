"""
Guardian models for student/child relationships and communications. Strictly tenant-scoped.
"""
from django.db import models
from apps.common.models import TenantScopedModel


class Guardian(TenantScopedModel):
    user = models.OneToOneField(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="guardian_profile",
    )
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    email = models.EmailField(blank=True, default="")
    phone_number = models.CharField(max_length=50, db_index=True)
    occupation = models.CharField(max_length=100, blank=True, default="")
    address = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "guardians"
        ordering = ["first_name", "last_name"]

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.phone_number})"


class StudentGuardian(TenantScopedModel):
    REL_FATHER = "father"
    REL_MOTHER = "mother"
    REL_LEGAL_GUARDIAN = "legal_guardian"
    REL_OTHER = "other"

    RELATIONSHIP_CHOICES = (
        (REL_FATHER, "Father"),
        (REL_MOTHER, "Mother"),
        (REL_LEGAL_GUARDIAN, "Legal Guardian"),
        (REL_OTHER, "Other"),
    )

    student = models.ForeignKey(
        "students.Student",
        on_delete=models.CASCADE,
        related_name="guardian_links",
    )
    guardian = models.ForeignKey(
        Guardian,
        on_delete=models.CASCADE,
        related_name="student_links",
    )
    relationship = models.CharField(max_length=30, choices=RELATIONSHIP_CHOICES, default=REL_LEGAL_GUARDIAN)
    is_primary = models.BooleanField(default=False)
    is_emergency_contact = models.BooleanField(default=False)

    class Meta:
        db_table = "student_guardians"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "student", "guardian"],
                name="unique_tenant_student_guardian",
            )
        ]

    def __str__(self):
        return f"{self.guardian.first_name} ({self.relationship}) -> {self.student.first_name}"
