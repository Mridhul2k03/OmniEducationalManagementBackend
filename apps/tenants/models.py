"""
Tenant (Organization) domain model.
Represents an individual educational institution (School, College, University, etc.).
"""
from django.db import models
from apps.common.models import UUIDModel, TimeStampedModel, SoftDeletableModel


class Tenant(UUIDModel, TimeStampedModel, SoftDeletableModel):
    """
    Central Tenant/Organization entity.
    """
    TYPE_SCHOOL = "school"
    TYPE_COLLEGE = "college"
    TYPE_UNIVERSITY = "university"
    TYPE_INSTITUTE = "institute"
    TYPE_COACHING = "coaching"
    TYPE_ONLINE = "online"

    INSTITUTION_TYPE_CHOICES = (
        (TYPE_SCHOOL, "School (K-12)"),
        (TYPE_COLLEGE, "College / Higher Secondary"),
        (TYPE_UNIVERSITY, "University"),
        (TYPE_INSTITUTE, "Professional Institute"),
        (TYPE_COACHING, "Coaching Center / Academy"),
        (TYPE_ONLINE, "Online Tuition / Learning Provider"),
    )

    STATUS_ACTIVE = "active"
    STATUS_ONBOARDING = "onboarding"
    STATUS_SUSPENDED = "suspended"
    STATUS_ARCHIVED = "archived"

    STATUS_CHOICES = (
        (STATUS_ACTIVE, "Active"),
        (STATUS_ONBOARDING, "Onboarding"),
        (STATUS_SUSPENDED, "Suspended"),
        (STATUS_ARCHIVED, "Archived"),
    )

    name = models.CharField(max_length=255, db_index=True)
    legal_name = models.CharField(max_length=255, blank=True, default="")
    slug = models.SlugField(max_length=100, unique=True, db_index=True)
    institution_type = models.CharField(
        max_length=50,
        choices=INSTITUTION_TYPE_CHOICES,
        default=TYPE_SCHOOL,
        db_index=True,
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_ONBOARDING,
        db_index=True,
    )
    
    # Regional and Localization
    timezone = models.CharField(max_length=50, default="UTC")
    locale = models.CharField(max_length=10, default="en")
    currency = models.CharField(max_length=10, default="USD")

    # Branding & Contact
    logo_url = models.URLField(max_length=500, blank=True, default="")
    branding_metadata = models.JSONField(default=dict, blank=True)
    address = models.JSONField(default=dict, blank=True)
    contact_email = models.EmailField(blank=True, default="")
    contact_phone = models.CharField(max_length=50, blank=True, default="")
    subscription_reference = models.CharField(max_length=100, blank=True, default="")

    class Meta:
        db_table = "tenants"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["status"]),
            models.Index(fields=["institution_type"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.slug})"
