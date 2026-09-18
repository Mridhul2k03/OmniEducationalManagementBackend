"""
Serializers for Identity, Authentication, Tenant Memberships, and RBAC.
"""
from django.db import transaction
from django.utils.text import slugify
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from apps.accounts.models import User, Membership, Role, Permission, RolePermission, MembershipRole
from apps.tenants.models import Tenant
from apps.tenants.serializers import TenantSerializer
from apps.audit.services import log_audit_event


# Standard permission list for bootstrapping an educational institution
DEFAULT_PERMISSION_DEFINITIONS = [
    # Students
    ("students.view", "View Students", "students"),
    ("students.create", "Create Student / Start Admission", "students"),
    ("students.update", "Update Student Details", "students"),
    ("students.delete", "Archive / Delete Student", "students"),
    # Attendance
    ("attendance.mark", "Mark Daily / Class Attendance", "attendance"),
    ("attendance.view", "View Attendance Records", "attendance"),
    ("attendance.correct", "Approve / Correct Attendance", "attendance"),
    # Examinations & Marks
    ("exams.manage", "Create and Schedule Examinations", "examinations"),
    ("marks.enter", "Enter Examination Marks", "examinations"),
    ("marks.review", "Review Examination Marks", "examinations"),
    ("marks.publish", "Publish Examination Results", "examinations"),
    # Finance
    ("fees.view", "View Fee Structures and Invoices", "finance"),
    ("fees.create_invoice", "Generate Invoices", "finance"),
    ("fees.record_payment", "Record and Process Payments", "finance"),
    ("fees.refund", "Process Fee Refunds", "finance"),
    # Staff & Academics
    ("academics.manage", "Manage Academic Years, Classes, Sections", "academics"),
    ("staff.manage", "Manage Staff and Faculty", "staff"),
    # Reports & Administration
    ("reports.export", "Export Data and Reports", "reports"),
    ("users.manage_roles", "Manage Roles and Permissions", "accounts"),
]


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "phone_number",
            "avatar_url",
            "is_staff",
            "is_superuser",
            "created_at",
        ]
        read_only_fields = ["id", "is_staff", "is_superuser", "created_at"]


class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = ["id", "code", "name", "module", "description"]


class RoleSerializer(serializers.ModelSerializer):
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = Role
        fields = ["id", "code", "name", "description", "is_system_role", "permissions"]

    def get_permissions(self, obj):
        perms = Permission.objects.filter(role_permissions__role=obj)
        return PermissionSerializer(perms, many=True).data


class MembershipSerializer(serializers.ModelSerializer):
    tenant = TenantSerializer(read_only=True)
    roles = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = Membership
        fields = ["id", "tenant", "status", "is_default", "joined_at", "roles", "permissions"]

    def get_roles(self, obj):
        roles = Role.objects.filter(membership_roles__membership=obj)
        return [{"id": str(r.id), "code": r.code, "name": r.name} for r in roles]

    def get_permissions(self, obj):
        return list(obj.get_permissions())


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Custom JWT serializer enriching token payload and response with active tenant context and accessible memberships.
    """
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["email"] = user.email
        token["full_name"] = user.full_name
        token["is_superuser"] = user.is_superuser
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        user = self.user

        # Get active memberships
        memberships = Membership.objects.filter(
            user=user,
            status=Membership.STATUS_ACTIVE,
            is_deleted=False,
        ).select_related("tenant")

        accessible_tenants = []
        default_tenant = None

        for m in memberships:
            t_data = {
                "id": str(m.tenant.id),
                "name": m.tenant.name,
                "slug": m.tenant.slug,
                "institution_type": m.tenant.institution_type,
                "is_default": m.is_default,
            }
            accessible_tenants.append(t_data)
            if m.is_default and default_tenant is None:
                default_tenant = t_data

        if not default_tenant and accessible_tenants:
            default_tenant = accessible_tenants[0]

        data["user"] = UserSerializer(user).data
        data["accessible_tenants"] = accessible_tenants
        data["active_tenant"] = default_tenant

        return data


class RegisterInstitutionSerializer(serializers.Serializer):
    """
    Onboards a new Institution/Tenant with an Initial Administrator Account atomically.
    """
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    institution_name = serializers.CharField(max_length=255)
    institution_type = serializers.ChoiceField(choices=Tenant.INSTITUTION_TYPE_CHOICES, default=Tenant.TYPE_SCHOOL)
    slug = serializers.SlugField(max_length=100, required=False)

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value.lower()

    def validate(self, attrs):
        inst_name = attrs.get("institution_name")
        slug = attrs.get("slug") or slugify(inst_name)
        if Tenant.objects.filter(slug=slug).exists():
            raise serializers.ValidationError({"slug": f"The organization slug '{slug}' is already taken."})
        attrs["slug"] = slug
        return attrs

    def create(self, validated_data):
        with transaction.atomic():
            # 1. Create Tenant
            tenant = Tenant.objects.create(
                name=validated_data["institution_name"],
                slug=validated_data["slug"],
                institution_type=validated_data["institution_type"],
                status=Tenant.STATUS_ACTIVE,
                contact_email=validated_data["email"],
            )

            # 2. Create User
            user = User.objects.create_user(
                email=validated_data["email"],
                password=validated_data["password"],
                first_name=validated_data["first_name"],
                last_name=validated_data["last_name"],
            )

            # 3. Create Tenant Admin Role
            admin_role, _ = Role.objects.get_or_create(
                tenant=tenant,
                code=Role.CODE_INSTITUTION_ADMIN,
                defaults={"name": "Institution Administrator", "is_system_role": True},
            )

            # 4. Bootstrap Standard Permissions & Assign to Admin Role
            for code, name, module in DEFAULT_PERMISSION_DEFINITIONS:
                perm, _ = Permission.objects.get_or_create(
                    code=code,
                    defaults={"name": name, "module": module},
                )
                RolePermission.objects.get_or_create(role=admin_role, permission=perm)

            # 5. Create Active Membership
            membership = Membership.objects.create(
                user=user,
                tenant=tenant,
                status=Membership.STATUS_ACTIVE,
                is_default=True,
            )
            MembershipRole.objects.create(membership=membership, role=admin_role)

            # 6. Audit Logging
            log_audit_event(
                action="CREATE",
                resource_type="Tenant",
                resource_id=str(tenant.id),
                tenant=tenant,
                actor=user,
                description=f"Institution '{tenant.name}' registered with initial admin '{user.email}'.",
            )

            # 7. Generate JWT Tokens
            refresh = RefreshToken.for_user(user)
            refresh["email"] = user.email

            return {
                "user": UserSerializer(user).data,
                "tenant": TenantSerializer(tenant).data,
                "tokens": {
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                },
            }
