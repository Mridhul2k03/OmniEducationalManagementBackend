"""
Academic structure models: AcademicYear, Term, Department, Course, Subject, ClassCohort, Section.
All models are strictly tenant-scoped.
"""
from django.db import models
from apps.common.models import TenantScopedModel


class AcademicYear(TenantScopedModel):
    name = models.CharField(max_length=100)  # e.g. "2025-2026"
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False)

    class Meta:
        db_table = "academic_years"
        ordering = ["-start_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "name"],
                name="unique_tenant_academic_year",
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.tenant.name})"


class Term(TenantScopedModel):
    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.CASCADE,
        related_name="terms",
    )
    name = models.CharField(max_length=100)  # e.g. "Term 1", "Semester 1", "Fall 2025"
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False)

    class Meta:
        db_table = "academic_terms"
        ordering = ["start_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "academic_year", "name"],
                name="unique_tenant_term_name",
            )
        ]

    def __str__(self):
        return f"{self.academic_year.name} - {self.name}"


class Department(TenantScopedModel):
    name = models.CharField(max_length=150)  # e.g. "Computer Science", "Science", "Humanities"
    code = models.CharField(max_length=50)

    class Meta:
        db_table = "academic_departments"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "code"],
                name="unique_tenant_department_code",
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"


class Course(TenantScopedModel):
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name="courses",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=150)  # e.g. "B.Tech Computer Science", "High School Diploma"
    code = models.CharField(max_length=50)
    credits = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "academic_courses"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "code"],
                name="unique_tenant_course_code",
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"


class Subject(TenantScopedModel):
    TYPE_THEORY = "theory"
    TYPE_PRACTICAL = "practical"
    TYPE_LAB = "lab"

    TYPE_CHOICES = (
        (TYPE_THEORY, "Theory"),
        (TYPE_PRACTICAL, "Practical"),
        (TYPE_LAB, "Laboratory"),
    )

    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="subjects",
    )
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=50)
    subject_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_THEORY)

    class Meta:
        db_table = "academic_subjects"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "code"],
                name="unique_tenant_subject_code",
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"


class ClassCohort(TenantScopedModel):
    """
    Represents a grade, standard, or cohort. E.g. "Grade 10", "1st Year B.Sc".
    """
    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.CASCADE,
        related_name="classes",
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="classes",
    )
    name = models.CharField(max_length=100)

    class Meta:
        db_table = "academic_classes"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "academic_year", "name"],
                name="unique_tenant_class_cohort",
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.academic_year.name})"


class Section(TenantScopedModel):
    """
    Division or section of a class cohort. E.g. "Section A", "Batch 2026-1".
    """
    class_cohort = models.ForeignKey(
        ClassCohort,
        on_delete=models.CASCADE,
        related_name="sections",
    )
    name = models.CharField(max_length=50)  # e.g. "A", "B", "Alpha"
    room_number = models.CharField(max_length=50, blank=True, default="")
    capacity = models.PositiveIntegerField(default=40)

    class Meta:
        db_table = "academic_sections"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "class_cohort", "name"],
                name="unique_tenant_class_section",
            )
        ]

    def __str__(self):
        return f"{self.class_cohort.name} - Section {self.name}"
