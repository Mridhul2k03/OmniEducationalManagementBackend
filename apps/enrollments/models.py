"""
Student Enrollment domain model connecting students with academic years, classes, and sections.
"""
from django.db import models
from apps.common.models import TenantScopedModel


class Enrollment(TenantScopedModel):
    STATUS_ACTIVE = "active"
    STATUS_PROMOTED = "promoted"
    STATUS_REPEATING = "repeating"
    STATUS_TRANSFERRED = "transferred"
    STATUS_COMPLETED = "completed"

    STATUS_CHOICES = (
        (STATUS_ACTIVE, "Active"),
        (STATUS_PROMOTED, "Promoted"),
        (STATUS_REPEATING, "Repeating"),
        (STATUS_TRANSFERRED, "Transferred"),
        (STATUS_COMPLETED, "Completed"),
    )

    student = models.ForeignKey(
        "students.Student",
        on_delete=models.CASCADE,
        related_name="enrollments",
        db_index=True,
    )
    academic_year = models.ForeignKey(
        "academics.AcademicYear",
        on_delete=models.CASCADE,
        related_name="enrollments",
        db_index=True,
    )
    class_cohort = models.ForeignKey(
        "academics.ClassCohort",
        on_delete=models.CASCADE,
        related_name="enrollments",
    )
    section = models.ForeignKey(
        "academics.Section",
        on_delete=models.CASCADE,
        related_name="enrollments",
    )
    roll_number = models.CharField(max_length=50, blank=True, default="")
    enrolled_date = models.DateField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE, db_index=True)

    class Meta:
        db_table = "enrollments"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "student", "academic_year"],
                name="unique_tenant_student_yearly_enrollment",
            )
        ]
        indexes = [
            models.Index(fields=["class_cohort", "section"]),
        ]

    def __str__(self):
        return f"{self.student.full_name} -> {self.class_cohort.name} ({self.section.name})"
