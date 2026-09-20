"""
Custom User, Multi-Tenant Membership, Role, and Granular Permission models.
"""
import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from apps.common.models import UUIDModel, TimeStampedModel, SoftDeletableModel


class UserManager(BaseUserManager):
    """
    Custom user manager with email as unique identifier for authentication.
    """
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set.")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin, UUIDModel, TimeStampedModel, SoftDeletableModel):
    """
    Custom User entity. A user exists globally across the SaaS platform and can be
    a member of one or more Tenants with different roles.
    """
    email = models.EmailField(unique=True, db_index=True, max_length=255)
    first_name = models.CharField(max_length=150, blank=True, default="")
    last_name = models.CharField(max_length=150, blank=True, default="")
    phone_number = models.CharField(max_length=50, blank=True, default="", db_index=True)
    avatar_url = models.URLField(max_length=500, blank=True, default="")

    is_active = models.BooleanField(default=True, db_index=True)
    is_staff = models.BooleanField(default=False)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        db_table = "users"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["email"]),
            models.Index(fields=["phone_number"]),
        ]

    def __str__(self):
        return self.email

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.email


class Membership(UUIDModel, TimeStampedModel, SoftDeletableModel):
    """
    Links a User to a specific Tenant/Organization.
    Carries the membership status and connects to tenant-specific roles.
    """
    STATUS_ACTIVE = "active"
    STATUS_INVITED = "invited"
    STATUS_SUSPENDED = "suspended"
    STATUS_INACTIVE = "inactive"

    STATUS_CHOICES = (
        (STATUS_ACTIVE, "Active"),
        (STATUS_INVITED, "Invited"),
        (STATUS_SUSPENDED, "Suspended"),
        (STATUS_INACTIVE, "Inactive"),
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="memberships",
        db_index=True,
    )
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="memberships",
        db_index=True,
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
        db_index=True,
    )
    is_default = models.BooleanField(default=False)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "memberships"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "tenant"],
                name="unique_user_tenant_membership",
            )
        ]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["tenant", "status"]),
        ]

    def __str__(self):
        return f"{self.user.email} @ {self.tenant.slug} ({self.status})"

    def get_permissions(self):
        """
        Returns a set of permission codes associated with this membership's roles.
        """
        return set(
            Permission.objects.filter(
                role_permissions__role__membership_roles__membership=self
            ).values_list("code", flat=True)
        )


class Permission(UUIDModel, TimeStampedModel):
    """
    Granular permission entity representing a capability.
    Example codes: 'students.view', 'attendance.mark', 'marks.publish'
    """
    code = models.CharField(max_length=100, unique=True, db_index=True)
    name = models.CharField(max_length=150)
    module = models.CharField(max_length=50, db_index=True)
    description = models.TextField(blank=True, default="")

    class Meta:
        db_table = "permissions"
        ordering = ["module", "code"]

    def __str__(self):
        return f"{self.code} ({self.name})"


class Role(UUIDModel, TimeStampedModel, SoftDeletableModel):
    """
    Role entity. Can be system-wide default (tenant=None) or tenant-customized.
    """
    CODE_SUPER_ADMIN = "super_admin"
    CODE_INSTITUTION_SUPER_ADMIN = "institution_super_admin"
    CODE_INSTITUTION_ADMIN = "institution_admin"
    CODE_PRINCIPAL = "principal"
    CODE_TEACHER = "teacher"
    CODE_ACCOUNTANT = "accountant"
    CODE_STUDENT = "student"
    CODE_PARENT = "parent"
    CODE_LIBRARIAN = "librarian"

    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="roles",
        db_index=True,
    )
    code = models.CharField(max_length=50, db_index=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, default="")
    is_system_role = models.BooleanField(default=False)

    class Meta:
        db_table = "roles"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "code"],
                name="unique_tenant_role_code",
            )
        ]
        indexes = [
            models.Index(fields=["code"]),
        ]

    def __str__(self):
        tenant_str = self.tenant.slug if self.tenant else "System"
        return f"{self.name} [{self.code}] ({tenant_str})"


class RolePermission(UUIDModel, TimeStampedModel):
    """
    Maps permissions to roles.
    """
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name="role_permissions",
        db_index=True,
    )
    permission = models.ForeignKey(
        Permission,
        on_delete=models.CASCADE,
        related_name="role_permissions",
        db_index=True,
    )

    class Meta:
        db_table = "role_permissions"
        constraints = [
            models.UniqueConstraint(
                fields=["role", "permission"],
                name="unique_role_permission",
            )
        ]


class MembershipRole(UUIDModel, TimeStampedModel):
    """
    Assigns one or more roles to a user's membership within a specific tenant.
    """
    membership = models.ForeignKey(
        Membership,
        on_delete=models.CASCADE,
        related_name="membership_roles",
        db_index=True,
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name="membership_roles",
        db_index=True,
    )

    class Meta:
        db_table = "membership_roles"
        constraints = [
            models.UniqueConstraint(
                fields=["membership", "role"],
                name="unique_membership_role",
            )
        ]
