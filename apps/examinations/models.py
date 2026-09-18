"""
Examination and Grading domain models. Strictly tenant-scoped.
"""
from django.db import models
from django.core.exceptions import ValidationError
from apps.common.models import TenantScopedModel


class GradeScale(TenantScopedModel):
    name = models.CharField(max_length=100)  # e.g. "Standard GPA Scale", "CBSE Grading"
    description = models.TextField(blank=True, default="")
    # rules format: [{"grade": "A+", "min_percent": 90, "max_percent": 100, "grade_point": 4.0}, ...]
    rules = models.JSONField(default=list)

    class Meta:
        db_table = "grade_scales"

    def __str__(self):
        return self.name


class Exam(TenantScopedModel):
    STATUS_DRAFT = "draft"
    STATUS_SCHEDULED = "scheduled"
    STATUS_ONGOING = "ongoing"
    STATUS_COMPLETED = "completed"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = (
        (STATUS_DRAFT, "Draft"),
        (STATUS_SCHEDULED, "Scheduled"),
        (STATUS_ONGOING, "Ongoing"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_CANCELLED, "Cancelled"),
    )

    academic_year = models.ForeignKey(
        "academics.AcademicYear",
        on_delete=models.CASCADE,
        related_name="exams",
    )
    term = models.ForeignKey(
        "academics.Term",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="exams",
    )
    class_cohort = models.ForeignKey(
        "academics.ClassCohort",
        on_delete=models.CASCADE,
        related_name="exams",
    )
    name = models.CharField(max_length=150)  # e.g. "Midterm Examination Fall 2026"
    exam_type = models.CharField(max_length=50, default="standard")
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT, db_index=True)
    
    # Publication & Locking
    is_published = models.BooleanField(default=False, db_index=True)
    published_at = models.DateTimeField(null=True, blank=True)
    published_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="published_exams",
    )

    class Meta:
        db_table = "exams"
        ordering = ["-start_date"]

    def __str__(self):
        return f"{self.name} - {self.class_cohort.name}"


class ExamSubject(TenantScopedModel):
    exam = models.ForeignKey(
        Exam,
        on_delete=models.CASCADE,
        related_name="exam_subjects",
    )
    subject = models.ForeignKey(
        "academics.Subject",
        on_delete=models.CASCADE,
        related_name="exam_schedules",
    )
    exam_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    max_marks = models.DecimalField(max_digits=6, decimal_places=2, default=100.0)
    passing_marks = models.DecimalField(max_digits=6, decimal_places=2, default=40.0)

    class Meta:
        db_table = "exam_subjects"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "exam", "subject"],
                name="unique_tenant_exam_subject",
            )
        ]

    def __str__(self):
        return f"{self.exam.name} - {self.subject.name}"


class Mark(TenantScopedModel):
    STATUS_DRAFT = "draft"
    STATUS_SUBMITTED = "submitted"
    STATUS_APPROVED = "approved"

    STATUS_CHOICES = (
        (STATUS_DRAFT, "Draft"),
        (STATUS_SUBMITTED, "Submitted for Review"),
        (STATUS_APPROVED, "Approved"),
    )

    exam_subject = models.ForeignKey(
        ExamSubject,
        on_delete=models.CASCADE,
        related_name="marks",
    )
    student = models.ForeignKey(
        "students.Student",
        on_delete=models.CASCADE,
        related_name="exam_marks",
    )
    marks_obtained = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    is_absent = models.BooleanField(default=False)
    remarks = models.CharField(max_length=255, blank=True, default="")
    entered_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="entered_marks",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)

    class Meta:
        db_table = "marks"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "exam_subject", "student"],
                name="unique_tenant_exam_subject_student_mark",
            )
        ]

    def clean(self):
        if not self.is_absent:
            if self.marks_obtained is None:
                raise ValidationError("Marks obtained must be provided unless the student is absent.")
            if self.marks_obtained < 0:
                raise ValidationError("Marks obtained cannot be negative.")
            if self.marks_obtained > self.exam_subject.max_marks:
                raise ValidationError(f"Marks obtained ({self.marks_obtained}) cannot exceed maximum marks ({self.exam_subject.max_marks}).")

    def save(self, *args, **kwargs):
        # Prevent editing marks if exam is published
        if self.exam_subject.exam.is_published:
            raise ValidationError("Cannot modify marks for an exam that has already been published.")
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student.full_name} - {self.exam_subject.subject.name}: {self.marks_obtained}"
