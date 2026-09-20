"""
Serializers for Platform SuperAdmin Console.
Provides administrative control over users, organizations/tenants, memberships, and global audit streams.
"""
from django.db import transaction
from django.utils.text import slugify
from rest_framework import serializers
from apps.accounts.models import User, Membership, Role, MembershipRole
from apps.tenants.models import Tenant
from apps.students.models import Student
from apps.staff.models import Staff
from apps.finance.models import Invoice
from apps.audit.models import AuditLog


class PlatformUserMembershipSerializer(serializers.ModelSerializer):
    tenant_id = serializers.UUIDField(source="tenant.id", read_only=True)
    tenant_name = serializers.CharField(source="tenant.name", read_only=True)
    tenant_slug = serializers.CharField(source="tenant.slug", read_only=True)
    roles = serializers.SerializerMethodField()

    class Meta:
        model = Membership
        fields = ["id", "tenant_id", "tenant_name", "tenant_slug", "status", "is_default", "joined_at", "roles"]

    def get_roles(self, obj):
        roles = Role.objects.filter(membership_roles__membership=obj)
        return [{"id": str(r.id), "code": r.code, "name": r.name} for r in roles]


class PlatformUserSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    memberships = PlatformUserMembershipSerializer(many=True, read_only=True)

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
            "is_active",
            "is_staff",
            "is_superuser",
            "created_at",
            "memberships",
        ]
        read_only_fields = ["id", "created_at"]


class PlatformUserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, min_length=8)
    tenant_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    role_code = serializers.CharField(write_only=True, required=False, default="institute_admin")

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "password",
            "first_name",
            "last_name",
            "phone_number",
            "is_active",
            "is_staff",
            "is_superuser",
            "tenant_id",
            "role_code",
        ]

    def create(self, validated_data):
        password = validated_data.pop("password")
        tenant_id = validated_data.pop("tenant_id", None)
        role_code = validated_data.pop("role_code", "institute_admin")

        with transaction.atomic():
            user = User.objects.create_user(
                email=validated_data["email"],
                password=password,
                first_name=validated_data.get("first_name", ""),
                last_name=validated_data.get("last_name", ""),
                phone_number=validated_data.get("phone_number", ""),
                is_active=validated_data.get("is_active", True),
                is_staff=validated_data.get("is_staff", False),
                is_superuser=validated_data.get("is_superuser", False),
            )

            if tenant_id:
                tenant = Tenant.objects.filter(id=tenant_id, is_deleted=False).first()
                if tenant:
                    membership, _ = Membership.objects.get_or_create(
                        user=user,
                        tenant=tenant,
                        defaults={"status": Membership.STATUS_ACTIVE, "is_default": True},
                    )
                    role = Role.objects.filter(tenant=tenant, code=role_code, is_deleted=False).first()
                    if not role:
                        from apps.accounts.serializers import bootstrap_tenant_roles_and_permissions
                        bootstrap_tenant_roles_and_permissions(tenant)
                        role = Role.objects.filter(tenant=tenant, code=role_code, is_deleted=False).first()
                    if not role:
                        role = Role.objects.filter(is_system_role=True, code=role_code).first()
                    if not role:
                        role = Role.objects.filter(tenant=tenant).first()
                    if role:
                        MembershipRole.objects.get_or_create(membership=membership, role=role)

            return user


class PlatformUserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "first_name",
            "last_name",
            "phone_number",
            "avatar_url",
            "is_active",
            "is_staff",
            "is_superuser",
        ]


class PlatformPasswordResetSerializer(serializers.Serializer):
    new_password = serializers.CharField(required=True, min_length=8)

    def validate_new_password(self, value):
        if len(value) < 8:
            raise serializers.ValidationError("Password must be at least 8 characters.")
        return value


class PlatformAssignTenantSerializer(serializers.Serializer):
    tenant_id = serializers.UUIDField(required=True)
    role_code = serializers.CharField(required=False, default="faculty")
    is_default = serializers.BooleanField(required=False, default=False)


class PlatformTenantAdminSerializer(serializers.ModelSerializer):
    students_count = serializers.SerializerMethodField()
    staff_count = serializers.SerializerMethodField()
    invoices_count = serializers.SerializerMethodField()
    users_count = serializers.SerializerMethodField()

    class Meta:
        model = Tenant
        fields = [
            "id",
            "name",
            "legal_name",
            "slug",
            "institution_type",
            "status",
            "timezone",
            "locale",
            "currency",
            "logo_url",
            "branding_metadata",
            "address",
            "contact_email",
            "contact_phone",
            "subscription_reference",
            "created_at",
            "updated_at",
            "students_count",
            "staff_count",
            "invoices_count",
            "users_count",
        ]

    def get_students_count(self, obj):
        return Student.objects.filter(tenant=obj, is_deleted=False).count()

    def get_staff_count(self, obj):
        return Staff.objects.filter(tenant=obj, is_deleted=False).count()

    def get_invoices_count(self, obj):
        return Invoice.objects.filter(tenant=obj, is_deleted=False).count()

    def get_users_count(self, obj):
        return Membership.objects.filter(tenant=obj, is_deleted=False, status=Membership.STATUS_ACTIVE).count()


class PlatformTenantCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    legal_name = serializers.CharField(max_length=255, required=False, default="", allow_blank=True)
    slug = serializers.CharField(max_length=100, required=False, allow_blank=True, allow_null=True)
    institution_type = serializers.ChoiceField(choices=Tenant.INSTITUTION_TYPE_CHOICES, default=Tenant.TYPE_SCHOOL)
    currency = serializers.CharField(max_length=10, default="USD")
    timezone = serializers.CharField(max_length=50, default="UTC")
    contact_email = serializers.EmailField(required=False, default="", allow_blank=True)
    contact_phone = serializers.CharField(max_length=50, required=False, default="", allow_blank=True)
    subscription_plan = serializers.CharField(max_length=50, default="Enterprise")
    
    # Optional Initial Admin Account
    admin_email = serializers.EmailField(required=False, allow_blank=True)
    admin_password = serializers.CharField(required=False, allow_blank=True, min_length=8)
    admin_first_name = serializers.CharField(required=False, default="Admin", allow_blank=True)
    admin_last_name = serializers.CharField(required=False, default="User", allow_blank=True)

    def validate_slug(self, value):
        if not value or not str(value).strip():
            return ""
        s = slugify(value)
        if Tenant.objects.filter(slug=s, is_deleted=False).exists():
            raise serializers.ValidationError("An organization with this slug already exists.")
        return s

    def create(self, validated_data):
        name = validated_data["name"]
        slug_raw = validated_data.get("slug")
        if not slug_raw or not str(slug_raw).strip():
            slug_raw = name
        slug = slugify(slug_raw)
        
        # Ensure unique slug
        base_slug = slug
        counter = 1
        while Tenant.objects.filter(slug=slug, is_deleted=False).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1

        admin_email = validated_data.get("admin_email")
        admin_password = validated_data.get("admin_password")

        with transaction.atomic():
            tenant = Tenant.objects.create(
                name=name,
                legal_name=validated_data.get("legal_name", name),
                slug=slug,
                institution_type=validated_data.get("institution_type", Tenant.TYPE_SCHOOL),
                currency=validated_data.get("currency", "USD"),
                timezone=validated_data.get("timezone", "UTC"),
                contact_email=validated_data.get("contact_email", ""),
                contact_phone=validated_data.get("contact_phone", ""),
                status=Tenant.STATUS_ACTIVE,
                subscription_reference=validated_data.get("subscription_plan", "Enterprise"),
            )

            # Create default roles for the new tenant
            role_admin, _ = Role.objects.get_or_create(
                tenant=tenant,
                code="institute_admin",
                defaults={"name": "Institution Administrator", "is_system_role": True},
            )
            Role.objects.get_or_create(
                tenant=tenant,
                code="faculty",
                defaults={"name": "Faculty / Instructor", "is_system_role": True},
            )
            Role.objects.get_or_create(
                tenant=tenant,
                code="student",
                defaults={"name": "Student", "is_system_role": True},
            )
            Role.objects.get_or_create(
                tenant=tenant,
                code="accountant",
                defaults={"name": "Accountant / Bursar", "is_system_role": True},
            )

            # Provision initial admin user if credentials provided
            if admin_email and admin_password:
                admin_user, _ = User.objects.get_or_create(
                    email=admin_email,
                    defaults={
                        "first_name": validated_data.get("admin_first_name", "Admin"),
                        "last_name": validated_data.get("admin_last_name", "User"),
                        "is_active": True,
                    }
                )
                admin_user.set_password(admin_password)
                admin_user.save()

                membership, _ = Membership.objects.get_or_create(
                    user=admin_user,
                    tenant=tenant,
                    defaults={"status": Membership.STATUS_ACTIVE, "is_default": True},
                )
                MembershipRole.objects.get_or_create(membership=membership, role=role_admin)

            return tenant


class PlatformTenantUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = [
            "name",
            "legal_name",
            "institution_type",
            "status",
            "currency",
            "timezone",
            "logo_url",
            "contact_email",
            "contact_phone",
            "subscription_reference",
            "branding_metadata",
            "address",
        ]


class PlatformAuditLogSerializer(serializers.ModelSerializer):
    actor_email = serializers.CharField(source="actor.email", read_only=True, default="System")
    actor_name = serializers.CharField(source="actor.full_name", read_only=True, default="System")
    tenant_name = serializers.CharField(source="tenant.name", read_only=True, default="Global Platform")
    tenant_slug = serializers.CharField(source="tenant.slug", read_only=True, default="global")

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "tenant",
            "tenant_name",
            "tenant_slug",
            "actor",
            "actor_email",
            "actor_name",
            "action",
            "resource_type",
            "resource_id",
            "description",
            "changes",
            "ip_address",
            "user_agent",
            "request_id",
            "created_at",
        ]
