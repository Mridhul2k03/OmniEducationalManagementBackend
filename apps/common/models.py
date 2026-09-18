"""
Abstract base models and managers enforcing UUIDs, timestamps, soft-deletion, and tenant isolation.
"""
import uuid
from django.db import models
from django.utils import timezone
from apps.common.context import get_current_tenant


class UUIDModel(models.Model):
    """
    Abstract base model providing a UUID primary key.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class TimeStampedModel(models.Model):
    """
    Abstract base model providing self-updating created_at and updated_at fields.
    """
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SoftDeletableQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_deleted=False)

    def deleted(self):
        return self.filter(is_deleted=True)


class SoftDeletableManager(models.Manager):
    def get_queryset(self):
        return SoftDeletableQuerySet(self.model, using=self._db).filter(is_deleted=False)

    def all_with_deleted(self):
        return SoftDeletableQuerySet(self.model, using=self._db)

    def deleted_only(self):
        return SoftDeletableQuerySet(self.model, using=self._db).filter(is_deleted=True)


class SoftDeletableModel(models.Model):
    """
    Abstract base model providing soft-deletion capability.
    """
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = SoftDeletableManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True

    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=["is_deleted", "deleted_at"])

    def restore(self):
        self.is_deleted = False
        self.deleted_at = None
        self.save(update_fields=["is_deleted", "deleted_at"])


class AuditedModel(models.Model):
    """
    Abstract base model tracking creator and last updater.
    """
    created_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(app_label)s_%(class)s_created",
        editable=False,
    )
    updated_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(app_label)s_%(class)s_updated",
        editable=False,
    )

    class Meta:
        abstract = True


class TenantQuerySet(SoftDeletableQuerySet):
    def for_current_tenant(self):
        tenant = get_current_tenant()
        if tenant is not None:
            return self.filter(tenant=tenant)
        return self

    def for_tenant(self, tenant):
        return self.filter(tenant=tenant)


class TenantManager(SoftDeletableManager):
    def get_queryset(self):
        qs = TenantQuerySet(self.model, using=self._db).filter(is_deleted=False)
        tenant = get_current_tenant()
        if tenant is not None:
            return qs.filter(tenant=tenant)
        return qs

    def unscoped(self):
        """Allows bypassing current tenant context for background worker or superadmin operations."""
        return TenantQuerySet(self.model, using=self._db)


class TenantScopedModel(UUIDModel, TimeStampedModel, SoftDeletableModel, AuditedModel):
    """
    Abstract base model enforcing strict multi-tenant boundary.
    Every tenant-owned entity MUST inherit from this model.
    """
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="%(app_label)s_%(class)s_set",
        db_index=True,
    )

    objects = TenantManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        # Enforce automatic tenant assignment from thread context if not already set
        if not self.tenant_id:
            current_tenant = get_current_tenant()
            if current_tenant:
                self.tenant = current_tenant
        super().save(*args, **kwargs)
