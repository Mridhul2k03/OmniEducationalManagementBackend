"""
AuditLog domain model for immutable compliance logging of critical events.
"""
from django.db import models
from apps.common.models import UUIDModel


class AuditLog(UUIDModel):
    """
    Immutable audit trail record for security, compliance, and dispute resolution.
    """
    ACTION_CREATE = "CREATE"
    ACTION_UPDATE = "UPDATE"
    ACTION_DELETE = "DELETE"
    ACTION_VIEW = "VIEW"
    ACTION_EXPORT = "EXPORT"
    ACTION_PUBLISH = "PUBLISH"
    ACTION_APPROVE = "APPROVE"
    ACTION_LOGIN = "LOGIN"
    ACTION_REJECT = "REJECT"

    ACTION_CHOICES = (
        (ACTION_CREATE, "Create"),
        (ACTION_UPDATE, "Update"),
        (ACTION_DELETE, "Delete"),
        (ACTION_VIEW, "View"),
        (ACTION_EXPORT, "Export"),
        (ACTION_PUBLISH, "Publish"),
        (ACTION_APPROVE, "Approve"),
        (ACTION_LOGIN, "Login"),
        (ACTION_REJECT, "Reject"),
    )

    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="audit_logs",
        db_index=True,
    )
    actor = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_actions",
        db_index=True,
    )
    action = models.CharField(max_length=50, choices=ACTION_CHOICES, db_index=True)
    resource_type = models.CharField(max_length=100, db_index=True)
    resource_id = models.CharField(max_length=100, db_index=True)
    description = models.TextField(blank=True, default="")
    changes = models.JSONField(default=dict, blank=True)
    
    # Network & Traceability
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True, default="")
    request_id = models.CharField(max_length=100, blank=True, default="", db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "audit_logs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "-created_at"]),
            models.Index(fields=["resource_type", "resource_id"]),
            models.Index(fields=["action"]),
        ]

    def __str__(self):
        actor_email = self.actor.email if self.actor else "System"
        return f"[{self.created_at}] {actor_email} - {self.action} {self.resource_type}:{self.resource_id}"
