"""
Staff / Faculty domain model. Strictly tenant-scoped.
"""
from django.db import models
from apps.common.models import TenantScopedModel


class Staff(TenantScopedModel):
    TYPE_FULL_TIME = "full_time"
    TYPE_PART_TIME = "part_time"
    TYPE_CONTRACT = "contract"
    TYPE_VISITING = "visiting"

    EMPLOYMENT_TYPE_CHOICES = (
        (TYPE_FULL_TIME, "Full Time"),
        (TYPE_PART_TIME, "Part Time"),
        (TYPE_CONTRACT, "Contract"),
        (TYPE_VISITING, "Visiting"),
    )

    STATUS_ACTIVE = "active"
    STATUS_ON_LEAVE = "on_leave"
    STATUS_RESIGNED = "resigned"
    STATUS_TERMINATED = "terminated"

    STATUS_CHOICES = (
        (STATUS_ACTIVE, "Active"),
        (STATUS_ON_LEAVE, "On Leave"),
        (STATUS_RESIGNED, "Resigned"),
        (STATUS_TERMINATED, "Terminated"),
    )

    user = models.OneToOneField(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="staff_profile",
    )
    employee_id = models.CharField(max_length=50, db_index=True)
    department = models.ForeignKey(
        "academics.Department",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="staff_members",
    )
    designation = models.CharField(max_length=100)
    qualification = models.CharField(max_length=200, blank=True, default="")
    joined_date = models.DateField()
    employment_type = models.CharField(max_length=20, choices=EMPLOYMENT_TYPE_CHOICES, default=TYPE_FULL_TIME)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)

    class Meta:
        db_table = "staff"
        ordering = ["employee_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "employee_id"],
                name="unique_tenant_staff_employee_id",
            )
        ]

    def __str__(self):
        return f"{self.employee_id} - {self.user.full_name} ({self.designation})"
