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
    # Administration & Security
    ("users.manage_admins", "Create and Manage Admin Accounts", "administration"),
    ("users.manage_roles", "Manage Roles and Permissions Matrix", "administration"),
    ("users.manage_staff", "Add, Edit, Deactivate Staff Members", "administration"),
    ("users.view", "View Institution Users and Staff", "administration"),
    ("tenant.manage_settings", "Manage Institution Settings & Profile", "administration"),
    ("audit.view", "View Institution Audit Trail and Activities", "audit"),
    # Students / Learners
    ("students.view", "View Students / Learners", "students"),
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
    # Reports
    ("reports.export", "Export Data and Reports", "reports"),
]


def bootstrap_tenant_roles_and_permissions(tenant):
    """
    Bootstraps all standard permissions and default roles for a tenant institution.
    """
    perm_objs = {}
    for code, name, module in DEFAULT_PERMISSION_DEFINITIONS:
        perm, _ = Permission.objects.get_or_create(
            code=code,
            defaults={"name": name, "module": module},
        )
        perm_objs[code] = perm

    # 1. Institution Super Admin (All permissions)
    super_admin_role, _ = Role.objects.get_or_create(
        tenant=tenant,
        code=Role.CODE_INSTITUTION_SUPER_ADMIN,
        defaults={"name": "Institution Super Admin", "description": "Complete institutional control and authority", "is_system_role": True},
    )
    for perm in perm_objs.values():
        RolePermission.objects.get_or_create(role=super_admin_role, permission=perm)

    # 2. Delegated Institution Admin
    admin_role, _ = Role.objects.get_or_create(
        tenant=tenant,
        code=Role.CODE_INSTITUTION_ADMIN,
        defaults={"name": "Institution Administrator", "description": "Delegated administrator for operational management", "is_system_role": True},
    )
    admin_perm_codes = [
        "users.manage_staff", "users.view", "staff.manage", "students.view",
        "students.create", "students.update", "attendance.view", "attendance.correct",
        "exams.manage", "marks.review", "marks.publish", "fees.view",
        "academics.manage", "reports.export"
    ]
    for code in admin_perm_codes:
        if code in perm_objs:
            RolePermission.objects.get_or_create(role=admin_role, permission=perm_objs[code])

    # 3. Principal / Head
    principal_role, _ = Role.objects.get_or_create(
        tenant=tenant,
        code=Role.CODE_PRINCIPAL,
        defaults={"name": "Principal / Dean", "description": "Academic oversight and faculty head", "is_system_role": True},
    )
    principal_perm_codes = [
        "users.view", "staff.manage", "students.view", "students.create", "students.update",
        "attendance.view", "attendance.correct", "exams.manage", "marks.review",
        "marks.publish", "fees.view", "academics.manage", "reports.export"
    ]
    for code in principal_perm_codes:
        if code in perm_objs:
            RolePermission.objects.get_or_create(role=principal_role, permission=perm_objs[code])

    # 4. Teacher / Faculty
    faculty_role, _ = Role.objects.get_or_create(
        tenant=tenant,
        code="faculty",
        defaults={"name": "Faculty / Educator", "description": "Classroom instruction, attendance, marks", "is_system_role": True},
    )
    teacher_role, _ = Role.objects.get_or_create(
        tenant=tenant,
        code=Role.CODE_TEACHER,
        defaults={"name": "Teacher / Faculty", "description": "Teaching faculty member", "is_system_role": True},
    )
    faculty_perm_codes = ["students.view", "attendance.view", "attendance.mark", "exams.manage", "marks.enter", "marks.review"]
    for code in faculty_perm_codes:
        if code in perm_objs:
            RolePermission.objects.get_or_create(role=faculty_role, permission=perm_objs[code])
            RolePermission.objects.get_or_create(role=teacher_role, permission=perm_objs[code])

    # 5. Accountant
    accountant_role, _ = Role.objects.get_or_create(
        tenant=tenant,
        code=Role.CODE_ACCOUNTANT,
        defaults={"name": "Accountant / Bursar", "description": "Fee billing, invoices, payments", "is_system_role": True},
    )
    accountant_perm_codes = ["students.view", "fees.view", "fees.create_invoice", "fees.record_payment", "fees.refund", "reports.export"]
    for code in accountant_perm_codes:
        if code in perm_objs:
            RolePermission.objects.get_or_create(role=accountant_role, permission=perm_objs[code])

    # 6. Student
    Role.objects.get_or_create(
        tenant=tenant,
        code=Role.CODE_STUDENT,
        defaults={"name": "Student / Learner", "description": "Learner access to timetable, grades, fees", "is_system_role": True},
    )

    # 7. Parent
    Role.objects.get_or_create(
        tenant=tenant,
        code=Role.CODE_PARENT,
        defaults={"name": "Parent / Guardian", "description": "Parental portal access", "is_system_role": True},
    )

    return super_admin_role


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
            "is_active",
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
    permission_codes = serializers.ListField(
        child=serializers.CharField(),
        write_only=True,
        required=False,
    )

    class Meta:
        model = Role
        fields = ["id", "code", "name", "description", "is_system_role", "permissions", "permission_codes"]

    def get_permissions(self, obj):
        perms = Permission.objects.filter(role_permissions__role=obj)
        return PermissionSerializer(perms, many=True).data

    def create(self, validated_data):
        perm_codes = validated_data.pop("permission_codes", [])
        role = super().create(validated_data)
        if perm_codes:
            for code in perm_codes:
                perm = Permission.objects.filter(code=code).first()
                if perm:
                    RolePermission.objects.get_or_create(role=role, permission=perm)
        return role

    def update(self, instance, validated_data):
        perm_codes = validated_data.pop("permission_codes", None)
        role = super().update(instance, validated_data)
        if perm_codes is not None:
            RolePermission.objects.filter(role=role).delete()
            for code in perm_codes:
                perm = Permission.objects.filter(code=code).first()
                if perm:
                    RolePermission.objects.get_or_create(role=role, permission=perm)
        return role


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


class InstitutionUserSerializer(serializers.Serializer):
    """
    Rich representation of an institutional user, including their membership status,
    assigned roles, granular permissions, and staff dossier in the active tenant.
    """
    id = serializers.CharField(source="user.id")
    email = serializers.EmailField(source="user.email")
    first_name = serializers.CharField(source="user.first_name")
    last_name = serializers.CharField(source="user.last_name")
    full_name = serializers.CharField(source="user.full_name")
    phone_number = serializers.CharField(source="user.phone_number")
    avatar_url = serializers.CharField(source="user.avatar_url")
    is_active = serializers.BooleanField(source="user.is_active")
    membership_id = serializers.CharField(source="id")
    status = serializers.CharField()
    joined_at = serializers.DateTimeField()
    is_default = serializers.BooleanField()
    roles = serializers.SerializerMethodField()
    primary_role = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()
    is_institution_superadmin = serializers.SerializerMethodField()
    staff_profile = serializers.SerializerMethodField()

    def get_roles(self, obj):
        roles = Role.objects.filter(membership_roles__membership=obj)
        return [{"id": str(r.id), "code": r.code, "name": r.name} for r in roles]

    def get_primary_role(self, obj):
        roles = Role.objects.filter(membership_roles__membership=obj)
        # Prioritize institution_super_admin, then institution_admin
        for r in roles:
            if r.code in [Role.CODE_INSTITUTION_SUPER_ADMIN, Role.CODE_SUPER_ADMIN]:
                return {"code": r.code, "name": r.name}
        first = roles.first()
        if first:
            return {"code": first.code, "name": first.name}
        return {"code": "member", "name": "Member"}

    def get_permissions(self, obj):
        if obj.user.is_superuser:
            return ["*"]
        is_super = Role.objects.filter(
            membership_roles__membership=obj,
            code__in=[Role.CODE_INSTITUTION_SUPER_ADMIN, Role.CODE_SUPER_ADMIN]
        ).exists()
        if is_super:
            return ["*"]
        return list(obj.get_permissions())

    def get_is_institution_superadmin(self, obj):
        if obj.user.is_superuser:
            return True
        return Role.objects.filter(
            membership_roles__membership=obj,
            code__in=[Role.CODE_INSTITUTION_SUPER_ADMIN, Role.CODE_SUPER_ADMIN]
        ).exists()

    def get_staff_profile(self, obj):
        from apps.staff.models import Staff
        staff = Staff.objects.filter(user=obj.user, tenant=obj.tenant).select_related("department").first()
        if staff:
            return {
                "id": str(staff.id),
                "employee_id": staff.employee_id,
                "designation": staff.designation,
                "department": staff.department.name if staff.department else None,
                "employment_type": staff.employment_type,
                "status": staff.status,
            }
        return None


class InstitutionUserCreateSerializer(serializers.Serializer):
    """
    Creates a new user and membership in the active institution with specific role & permissions.
    """
    email = serializers.EmailField()
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, required=False, default="Password123!")
    phone_number = serializers.CharField(max_length=50, required=False, allow_blank=True, default="")
    role_code = serializers.CharField(max_length=50, default="faculty")
    permissions = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    designation = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    department_id = serializers.UUIDField(required=False, allow_null=True, default=None)
    employment_type = serializers.CharField(max_length=20, required=False, default="full_time")

    def validate_email(self, value):
        return value.strip().lower()

    def create(self, validated_data):
        from apps.staff.models import Staff
        from apps.accounts.permissions import get_or_resolve_tenant

        request = self.context.get("request")
        tenant = get_or_resolve_tenant(request)
        if not tenant:
            raise serializers.ValidationError("Active organization context is missing.")

        email = validated_data["email"]
        password = validated_data.get("password") or "Password123!"
        first_name = validated_data["first_name"].strip()
        last_name = validated_data["last_name"].strip()
        phone_number = validated_data.get("phone_number", "")
        role_code = validated_data.get("role_code", "faculty")
        perm_codes = validated_data.get("permissions", [])
        designation = validated_data.get("designation", "")
        department_id = validated_data.get("department_id")
        employment_type = validated_data.get("employment_type", "full_time")

        with transaction.atomic():
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    "first_name": first_name,
                    "last_name": last_name,
                    "phone_number": phone_number,
                    "is_active": True,
                }
            )
            if created:
                user.set_password(password)
                user.save()
            else:
                # Update name / phone if not set
                if not user.first_name:
                    user.first_name = first_name
                if not user.last_name:
                    user.last_name = last_name
                if phone_number and not user.phone_number:
                    user.phone_number = phone_number
                user.save()

            membership, _ = Membership.objects.get_or_create(
                user=user,
                tenant=tenant,
                defaults={"status": Membership.STATUS_ACTIVE, "is_default": True},
            )
            membership.status = Membership.STATUS_ACTIVE
            membership.save(update_fields=["status"])

            # Resolve Role
            role = Role.objects.filter(tenant=tenant, code=role_code, is_deleted=False).first()
            if not role:
                role = Role.objects.filter(is_system_role=True, code=role_code).first()
            if not role:
                # Create role dynamically for tenant
                role_name = role_code.replace("_", " ").title()
                role = Role.objects.create(
                    tenant=tenant,
                    code=role_code,
                    name=role_name,
                    is_system_role=False,
                )

            # Assign Role to Membership
            MembershipRole.objects.get_or_create(membership=membership, role=role)

            # Assign custom permissions if provided
            if perm_codes:
                for p_code in perm_codes:
                    perm = Permission.objects.filter(code=p_code).first()
                    if perm:
                        RolePermission.objects.get_or_create(role=role, permission=perm)

            # Create Staff record if designation provided or role is staff/faculty
            if designation or role_code in ["faculty", "teacher", "principal", "accountant", "librarian"]:
                desig = designation or role.name
                if not Staff.objects.filter(user=user, tenant=tenant).exists():
                    import datetime
                    count = Staff.objects.filter(tenant=tenant).count() + 1
                    emp_id = f"STF-{str(count).zfill(3)}"
                    seq = count
                    while Staff.objects.filter(tenant=tenant, employee_id=emp_id).exists():
                        seq += 1
                        emp_id = f"STF-{str(seq).zfill(3)}"

                    Staff.objects.create(
                        user=user,
                        tenant=tenant,
                        employee_id=emp_id,
                        designation=desig,
                        department_id=department_id,
                        employment_type=employment_type,
                        joined_date=datetime.date.today(),
                        status=Staff.STATUS_ACTIVE,
                    )

            log_audit_event(
                action="CREATE",
                resource_type="Membership",
                resource_id=str(membership.id),
                actor=request.user if request else None,
                tenant=tenant,
                description=f"Created user account '{user.email}' as '{role.name}' in '{tenant.name}'.",
                request=request,
            )

            return membership


class InstitutionUserUpdateSerializer(serializers.Serializer):
    """
    Updates an institutional user's profile, role, status, and custom permissions.
    """
    first_name = serializers.CharField(max_length=150, required=False)
    last_name = serializers.CharField(max_length=150, required=False)
    phone_number = serializers.CharField(max_length=50, required=False, allow_blank=True)
    status = serializers.ChoiceField(choices=Membership.STATUS_CHOICES, required=False)
    role_code = serializers.CharField(max_length=50, required=False)
    permissions = serializers.ListField(child=serializers.CharField(), required=False)
    designation = serializers.CharField(max_length=100, required=False, allow_blank=True)
    department_id = serializers.UUIDField(required=False, allow_null=True)


class InstitutionUserResetPasswordSerializer(serializers.Serializer):
    new_password = serializers.CharField(min_length=8)


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

        accessible_tenants = []
        default_tenant = None

        if user.is_superuser:
            all_tenants = Tenant.objects.filter(is_deleted=False)
            for t in all_tenants:
                t_data = {
                    "id": str(t.id),
                    "name": t.name,
                    "slug": t.slug,
                    "institution_type": t.institution_type,
                    "currency": t.currency,
                    "timezone": t.timezone,
                    "is_default": False,
                }
                accessible_tenants.append(t_data)
            if accessible_tenants:
                accessible_tenants[0]["is_default"] = True
                default_tenant = accessible_tenants[0]
        else:
            # Get active memberships
            memberships = Membership.objects.filter(
                user=user,
                status=Membership.STATUS_ACTIVE,
                is_deleted=False,
            ).select_related("tenant")

            for m in memberships:
                t_data = {
                    "id": str(m.tenant.id),
                    "name": m.tenant.name,
                    "slug": m.tenant.slug,
                    "institution_type": m.tenant.institution_type,
                    "currency": m.tenant.currency,
                    "timezone": m.tenant.timezone,
                    "is_default": m.is_default,
                }
                accessible_tenants.append(t_data)
                if m.is_default and default_tenant is None:
                    default_tenant = t_data

            if not default_tenant and accessible_tenants:
                default_tenant = accessible_tenants[0]

            if not accessible_tenants or not default_tenant:
                raise serializers.ValidationError(
                    "Your account is not assigned to any active educational institution. Please contact your administrator."
                )

        from apps.students.models import Student
        from apps.staff.models import Staff

        # Detect Student Profile
        student_obj = Student.objects.filter(user=user, is_deleted=False).first()
        # Detect Staff Profile
        staff_obj = Staff.objects.filter(user=user, is_deleted=False).first()

        profile_type = "admin"
        student_data = None
        staff_data = None
        role_code = "super_admin" if user.is_superuser else "faculty"

        if student_obj:
            profile_type = "student"
            role_code = "student"
            student_data = {
                "id": str(student_obj.id),
                "admission_number": student_obj.admission_number,
                "full_name": student_obj.full_name,
                "status": student_obj.status,
            }
        elif staff_obj:
            profile_type = "staff"
            staff_data = {
                "id": str(staff_obj.id),
                "employee_id": staff_obj.employee_id,
                "designation": staff_obj.designation,
                "status": staff_obj.status,
            }

        # Check membership roles for active tenant
        if default_tenant and "id" in default_tenant:
            membership = Membership.objects.filter(user=user, tenant_id=default_tenant["id"], is_deleted=False).first()
            if membership:
                roles = Role.objects.filter(membership_roles__membership=membership)
                for r in roles:
                    if r.code in [Role.CODE_INSTITUTION_SUPER_ADMIN, Role.CODE_SUPER_ADMIN]:
                        role_code = Role.CODE_INSTITUTION_SUPER_ADMIN
                        profile_type = "admin"
                        break
                if role_code not in [Role.CODE_INSTITUTION_SUPER_ADMIN, Role.CODE_SUPER_ADMIN] and roles.exists():
                    primary = roles.first()
                    role_code = primary.code
                    if primary.code == "student":
                        profile_type = "student"

        data["user"] = UserSerializer(user).data
        data["role"] = role_code
        data["profile_type"] = profile_type
        data["student_profile"] = student_data
        data["staff_profile"] = staff_data
        data["accessible_tenants"] = accessible_tenants
        data["active_tenant"] = default_tenant

        return data


class RegisterInstitutionSerializer(serializers.Serializer):
    """
    Onboards a new Institution/Tenant with an Initial Institution Super Admin Account atomically.
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

            # 3. Bootstrap All Roles and Permissions
            super_admin_role = bootstrap_tenant_roles_and_permissions(tenant)

            # 4. Create Active Membership with Institution Super Admin Role
            membership = Membership.objects.create(
                user=user,
                tenant=tenant,
                status=Membership.STATUS_ACTIVE,
                is_default=True,
            )
            MembershipRole.objects.create(membership=membership, role=super_admin_role)

            # 5. Audit Logging
            log_audit_event(
                action="CREATE",
                resource_type="Tenant",
                resource_id=str(tenant.id),
                tenant=tenant,
                actor=user,
                description=f"Institution '{tenant.name}' registered with initial Super Admin '{user.email}'.",
            )

            # 6. Generate JWT Tokens
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

