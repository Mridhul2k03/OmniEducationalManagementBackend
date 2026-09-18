"""
Attendance tracking and correction domain models. Strictly tenant-scoped.
"""
from django.db import models
from apps.common.models import TenantScopedModel


class AttendanceRecord(TenantScopedModel):
    STATUS_PRESENT = "present"
    STATUS_ABSENT = "absent"
    STATUS_LATE = "late"
    STATUS_EXCUSED = "excused"
    STATUS_HALF_DAY = "half_day"

    STATUS_CHOICES = (
        (STATUS_PRESENT, "Present"),
        (STATUS_ABSENT, "Absent"),
        (STATUS_LATE, "Late"),
        (STATUS_EXCUSED, "Excused"),
        (STATUS_HALF_DAY, "Half Day"),
    )

    student = models.ForeignKey(
        "students.Student",
        on_delete=models.CASCADE,
        related_name="attendance_records",
        db_index=True,
    )
    section = models.ForeignKey(
        "academics.Section",
        on_delete=models.CASCADE,
        related_name="attendance_records",
        db_index=True,
    )
    subject = models.ForeignKey(
        "academics.Subject",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attendance_records",
    )
    date = models.DateField(db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PRESENT, db_index=True)
    remarks = models.CharField(max_length=255, blank=True, default="")
    marked_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="marked_attendance_records",
    )

    class Meta:
        db_table = "attendance_records"
        ordering = ["-date", "student__admission_number"]
        indexes = [
            models.Index(fields=["tenant", "date"]),
            models.Index(fields=["section", "date"]),
            models.Index(fields=["student", "date"]),
        ]
        # Prevents duplicate attendance entries for same student, date, and subject (or daily)
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "student", "section", "subject", "date"],
                name="unique_tenant_student_daily_subject_attendance",
            )
        ]

    def __str__(self):
        return f"{self.date} - {self.student.full_name} ({self.status})"


class AttendanceCorrectionRequest(TenantScopedModel):
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"

    STATUS_CHOICES = (
        (STATUS_PENDING, "Pending Review"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
    )

    attendance_record = models.ForeignKey(
        AttendanceRecord,
        on_delete=models.CASCADE,
        related_name="correction_requests",
    )
    requested_status = models.CharField(max_length=20, choices=AttendanceRecord.STATUS_CHOICES)
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    requested_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="requested_attendance_corrections",
    )
    reviewed_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_attendance_corrections",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "attendance_correction_requests"
        ordering = ["-created_at"]
