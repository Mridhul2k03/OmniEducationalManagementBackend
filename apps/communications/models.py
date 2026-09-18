"""
Communications and Notifications domain models. Strictly tenant-scoped.
"""
from django.db import models
from apps.common.models import TenantScopedModel


class Announcement(TenantScopedModel):
    AUDIENCE_ALL = "all"
    AUDIENCE_STUDENTS = "students"
    AUDIENCE_TEACHERS = "teachers"
    AUDIENCE_PARENTS = "parents"

    AUDIENCE_CHOICES = (
        (AUDIENCE_ALL, "All Institution Members"),
        (AUDIENCE_STUDENTS, "Students Only"),
        (AUDIENCE_TEACHERS, "Faculty & Staff Only"),
        (AUDIENCE_PARENTS, "Parents & Guardians Only"),
    )

    title = models.CharField(max_length=255)
    content = models.TextField()
    target_audience = models.CharField(max_length=20, choices=AUDIENCE_CHOICES, default=AUDIENCE_ALL)
    is_published = models.BooleanField(default=True)
    published_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "announcements"
        ordering = ["-published_at"]

    def __str__(self):
        return self.title


class Notification(TenantScopedModel):
    CHANNEL_IN_APP = "in_app"
    CHANNEL_EMAIL = "email"
    CHANNEL_SMS = "sms"
    CHANNEL_WHATSAPP = "whatsapp"

    CHANNEL_CHOICES = (
        (CHANNEL_IN_APP, "In-App"),
        (CHANNEL_EMAIL, "Email"),
        (CHANNEL_SMS, "SMS"),
        (CHANNEL_WHATSAPP, "WhatsApp"),
    )

    recipient = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="notifications",
        db_index=True,
    )
    title = models.CharField(max_length=255)
    message = models.TextField()
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES, default=CHANNEL_IN_APP)
    is_read = models.BooleanField(default=False, db_index=True)
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "notifications"
        ordering = ["-sent_at"]

    def __str__(self):
        return f"To: {self.recipient.email} - {self.title}"
