import datetime
import uuid
from django.db import transaction
from rest_framework import serializers
from apps.staff.models import Staff
from apps.accounts.models import User, Membership, Role, MembershipRole
from apps.tenants.models import Tenant
from apps.accounts.permissions import get_or_resolve_tenant


class StaffSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="user.full_name", read_only=True, default="")
    email = serializers.EmailField(required=False, allow_blank=True, allow_null=True)
    department_name = serializers.CharField(source="department.name", read_only=True, default="")
    first_name = serializers.CharField(max_length=150, required=False, write_only=True, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, write_only=True, allow_blank=True)
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), required=False, allow_null=True)
    employee_id = serializers.CharField(max_length=50, required=False, allow_blank=True)
    joined_date = serializers.DateField(required=False)

    class Meta:
        model = Staff
        fields = [
            "id",
            "employee_id",
            "user",
            "first_name",
            "last_name",
            "full_name",
            "email",
            "department",
            "department_name",
            "designation",
            "qualification",
            "joined_date",
            "employment_type",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.user:
            data["email"] = instance.user.email
            data["full_name"] = instance.user.full_name
            data["avatar_url"] = instance.user.avatar_url
        return data

    def validate(self, attrs):
        user_email = attrs.get("email")
        user_raw = attrs.get("user")
        request = self.context.get("request")
        tenant = attrs.get("tenant") or (get_or_resolve_tenant(request) if request else None)

        target_email = None
        if user_email and str(user_email).strip():
            target_email = str(user_email).strip().lower()
        elif isinstance(user_raw, dict) and user_raw.get("email"):
            target_email = str(user_raw["email"]).strip().lower()

        if target_email:
            existing_user = User.objects.filter(email__iexact=target_email).first()
            if existing_user and Staff.objects.filter(user=existing_user).exists():
                existing_staff = Staff.objects.filter(user=existing_user).first()
                raise serializers.ValidationError({
                    "email": f"A staff member with email '{target_email}' is already registered (Employee ID: {existing_staff.employee_id})."
                })

        employee_id = attrs.get("employee_id")
        if employee_id and tenant and Staff.objects.filter(tenant=tenant, employee_id=employee_id).exists():
            raise serializers.ValidationError({
                "employee_id": f"Employee ID '{employee_id}' is already in use in this institution."
            })

        return attrs

    def create(self, validated_data):
        first_name = validated_data.pop("first_name", "")
        last_name = validated_data.pop("last_name", "")
        user_email = validated_data.pop("email", None)
        user_raw = validated_data.pop("user", None)
        request = self.context.get("request")
        tenant = validated_data.get("tenant") or (get_or_resolve_tenant(request) if request else None)
        if not tenant:
            tenant = Tenant.objects.filter(is_deleted=False, status=Tenant.STATUS_ACTIVE).first() or Tenant.objects.filter(is_deleted=False).first()

        # Handle user resolution
        user = None
        if isinstance(user_raw, User):
            user = user_raw
        elif isinstance(user_raw, dict):
            user_email = user_raw.get("email") or user_email
            first_name = user_raw.get("first_name") or first_name
            last_name = user_raw.get("last_name") or last_name
        elif isinstance(user_raw, (str, uuid.UUID)):
            user = User.objects.filter(id=user_raw).first()

        with transaction.atomic():
            if not user:
                fn = first_name.strip() if first_name else "Faculty"
                ln = last_name.strip() if last_name else "Member"
                if not user_email or not str(user_email).strip():
                    tenant_slug = tenant.slug if tenant and hasattr(tenant, "slug") else "omni"
                    base_email = f"{fn.lower().replace(' ', '')}.{ln.lower().replace(' ', '')}@{tenant_slug}.edu"
                    user_email = base_email
                    counter = 1
                    while User.objects.filter(email__iexact=user_email).exists():
                        user_email = f"{fn.lower().replace(' ', '')}.{ln.lower().replace(' ', '')}{counter}@{tenant_slug}.edu"
                        counter += 1
                else:
                    user_email = str(user_email).strip().lower()

                existing_user = User.objects.filter(email__iexact=user_email).first()
                if existing_user:
                    if Staff.objects.filter(user=existing_user).exists():
                        existing_staff = Staff.objects.filter(user=existing_user).first()
                        raise serializers.ValidationError({
                            "email": f"A staff member with email '{user_email}' is already registered (Employee ID: {existing_staff.employee_id})."
                        })
                    user = existing_user
                else:
                    user = User.objects.create_user(
                        email=user_email,
                        password="Password123!",
                        first_name=fn,
                        last_name=ln,
                    )

            # Prevent duplicate OneToOne staff profile on same user
            if Staff.objects.filter(user=user).exists():
                existing_staff = Staff.objects.filter(user=user).first()
                raise serializers.ValidationError({
                    "email": f"A staff member with email '{user.email}' is already registered (Employee ID: {existing_staff.employee_id})."
                })

            if tenant and user:
                membership, _ = Membership.objects.get_or_create(
                    user=user,
                    tenant=tenant,
                    defaults={"status": Membership.STATUS_ACTIVE, "is_default": True},
                )
                faculty_role, _ = Role.objects.get_or_create(
                    tenant=tenant,
                    code="faculty",
                    defaults={"name": "Faculty / Educator", "is_system_role": True},
                )
                MembershipRole.objects.get_or_create(membership=membership, role=faculty_role)

            if not validated_data.get("employee_id"):
                count = Staff.objects.filter(tenant=tenant).count() + 1 if tenant else 1
                emp_id = f"FAC-{str(count).zfill(3)}"
                seq = count
                while Staff.objects.filter(tenant=tenant, employee_id=emp_id).exists():
                    seq += 1
                    emp_id = f"FAC-{str(seq).zfill(3)}"
                validated_data["employee_id"] = emp_id

            if not validated_data.get("joined_date"):
                validated_data["joined_date"] = datetime.date.today()

            validated_data["user"] = user
            if tenant:
                validated_data["tenant"] = tenant

            try:
                staff = Staff.objects.create(**validated_data)
            except Exception as e:
                if "UNIQUE constraint failed" in str(e) or "unique" in str(e).lower():
                    raise serializers.ValidationError({
                        "email": f"A staff profile for user '{user.email}' or employee ID '{validated_data.get('employee_id')}' already exists."
                    })
                raise
            return staff

