"""
Authentication, Identity, and RBAC views.
"""
from rest_framework import generics, viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from apps.accounts.models import User, Membership, Role, Permission
from apps.tenants.models import Tenant
from apps.accounts.serializers import (
    UserSerializer,
    MembershipSerializer,
    RoleSerializer,
    PermissionSerializer,
    CustomTokenObtainPairSerializer,
    RegisterInstitutionSerializer,
    InstitutionUserSerializer,
    InstitutionUserCreateSerializer,
    InstitutionUserUpdateSerializer,
    InstitutionUserResetPasswordSerializer,
    bootstrap_tenant_roles_and_permissions,
)
from apps.accounts.permissions import (
    IsInstitutionSuperAdmin,
    IsInstitutionAdmin,
    IsTenantMember,
    HasTenantPermission,
    get_or_resolve_tenant,
    is_user_institution_superadmin,
)
from apps.audit.services import log_audit_event


class RegisterInstitutionView(APIView):
    """
    Public onboarding endpoint: Registers a new institution and initial administrator.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RegisterInstitutionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        return Response(
            {
                "success": True,
                "message": "Institution registered successfully.",
                "data": result,
            },
            status=status.HTTP_201_CREATED,
        )


from django.conf import settings


def set_auth_cookies(response, access_token=None, refresh_token=None):
    """
    Sets HttpOnly cookies on the response for cookie-based authentication.
    """
    secure = not settings.DEBUG
    samesite = "Lax"
    if access_token:
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            secure=secure,
            samesite=samesite,
            max_age=3600,
            path="/",
        )
    if refresh_token:
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=secure,
            samesite=samesite,
            max_age=7 * 86400,
            path="/",
        )
    return response


def clear_auth_cookies(response):
    """
    Explicitly purges all authentication and session cookies with expired timestamps and matching flags.
    """
    secure = not settings.DEBUG
    samesite = "Lax"

    for cookie_name in ["access_token", "refresh_token", "sessionid", "csrftoken"]:
        response.delete_cookie(cookie_name, path="/", samesite=samesite)
        response.set_cookie(
            key=cookie_name,
            value="",
            httponly=True,
            secure=secure,
            samesite=samesite,
            max_age=0,
            expires="Thu, 01 Jan 1970 00:00:00 GMT",
            path="/",
        )
    return response


class CustomLoginView(TokenObtainPairView):
    """
    User login issuing JWT access/refresh tokens with accessible tenant memberships,
    and setting secure HttpOnly authentication cookies.
    """
    serializer_class = CustomTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            access_token = response.data.get("access")
            refresh_token = response.data.get("refresh")
            set_auth_cookies(response, access_token=access_token, refresh_token=refresh_token)
        return response


class CustomTokenRefreshView(TokenRefreshView):
    """
    Refreshes access token, reading refresh token from request body or cookie,
    and updating the HttpOnly access_token cookie.
    """
    def post(self, request, *args, **kwargs):
        data = request.data.copy() if hasattr(request.data, "copy") else dict(request.data)
        if not data.get("refresh") and "refresh_token" in request.COOKIES:
            data["refresh"] = request.COOKIES["refresh_token"]
            request._full_data = data

        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            access_token = response.data.get("access")
            refresh_token = response.data.get("refresh")
            set_auth_cookies(response, access_token=access_token, refresh_token=refresh_token)
        return response


class LogoutView(APIView):
    """
    Logs out the user, records audit trail, invalidates tokens, and clears all auth cookies.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        if request.user and request.user.is_authenticated:
            try:
                log_audit_event(
                    action="LOGOUT",
                    resource_type="User",
                    resource_id=str(request.user.id),
                    actor=request.user,
                    description=f"User '{request.user.email}' signed out.",
                    request=request,
                )
            except Exception:
                pass

        # Blacklist refresh token if provided
        refresh_token = request.data.get("refresh") or request.COOKIES.get("refresh_token")
        if refresh_token:
            try:
                from rest_framework_simplejwt.tokens import RefreshToken
                token = RefreshToken(refresh_token)
                token.blacklist()
            except Exception:
                pass

        response = Response({
            "success": True,
            "message": "Logged out successfully from backend session."
        }, status=status.HTTP_200_OK)

        clear_auth_cookies(response)
        return response

    def get(self, request):
        return self.post(request)


class AuthCheckView(APIView):
    """
    Cookie-based login check endpoint.
    Verifies if user has a valid HttpOnly access_token cookie or Bearer header.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        # Force DRF to eagerly run authentication backends
        # (AllowAny makes auth lazy, so request.user may remain AnonymousUser)
        try:
            request.user  # triggers lazy authentication
        except Exception:
            pass

        # If DRF auth didn't resolve, try manually from cookie/header
        if not request.user or not request.user.is_authenticated:
            from apps.accounts.authentication import CookieJWTAuthentication
            try:
                auth_result = CookieJWTAuthentication().authenticate(request)
                if auth_result:
                    request.user, _ = auth_result
            except Exception:
                pass

        if not request.user or not request.user.is_authenticated:
            return Response(
                {
                    "success": False,
                    "authenticated": False,
                    "message": "Unauthenticated session.",
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        from apps.accounts.permissions import get_or_resolve_tenant
        user = request.user
        tenant = get_or_resolve_tenant(request)

        memberships = Membership.objects.filter(
            user=user,
            status=Membership.STATUS_ACTIVE,
            is_deleted=False,
        ).select_related("tenant")

        active_membership = None
        if tenant:
            active_membership = memberships.filter(tenant=tenant).first()

        role_code = "super_admin" if user.is_superuser else "faculty"
        permissions_list = ["*"] if user.is_superuser else []
        is_inst_super = bool(user.is_superuser)

        if active_membership:
            roles = Role.objects.filter(membership_roles__membership=active_membership)
            # Find primary role
            for r in roles:
                if r.code in [Role.CODE_INSTITUTION_SUPER_ADMIN, Role.CODE_SUPER_ADMIN]:
                    role_code = Role.CODE_INSTITUTION_SUPER_ADMIN
                    is_inst_super = True
                    break
            if not is_inst_super and roles.exists():
                role_code = roles.first().code

            if is_inst_super:
                permissions_list = ["*"]
            else:
                permissions_list = list(active_membership.get_permissions())

        from apps.students.models import Student
        from apps.staff.models import Staff

        student_obj = Student.objects.filter(user=user, is_deleted=False).first()
        staff_obj = Staff.objects.filter(user=user, is_deleted=False).first()

        profile_type = "admin"
        student_data = None
        staff_data = None

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

        active_tenant_data = None
        if tenant:
            active_tenant_data = {
                "id": str(tenant.id),
                "name": tenant.name,
                "slug": tenant.slug,
                "institution_type": tenant.institution_type,
                "currency": tenant.currency,
                "timezone": tenant.timezone,
                "subscription_plan": tenant.subscription_reference or "Starter",
            }

        return Response({
            "success": True,
            "authenticated": True,
            "data": {
                "user": UserSerializer(user).data,
                "role": role_code,
                "profile_type": profile_type,
                "student_profile": student_data,
                "staff_profile": staff_data,
                "is_institution_superadmin": is_inst_super,
                "active_tenant": active_tenant_data,
                "permissions": permissions_list,
            }
        }, status=status.HTTP_200_OK)


class MeView(APIView):
    """
    Returns the currently authenticated user's profile, active tenant, and memberships.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from apps.accounts.permissions import get_or_resolve_tenant
    
        user = request.user
        tenant = get_or_resolve_tenant(request)

        memberships = Membership.objects.filter(
            user=user,
            status=Membership.STATUS_ACTIVE,
            is_deleted=False,
        ).select_related("tenant")

        active_membership = None
        if tenant:
            active_membership = memberships.filter(tenant=tenant).first()

        is_inst_super = bool(user.is_superuser)
        if active_membership:
            is_inst_super = is_inst_super or Role.objects.filter(
                membership_roles__membership=active_membership,
                code__in=[Role.CODE_INSTITUTION_SUPER_ADMIN, Role.CODE_SUPER_ADMIN],
            ).exists()

        accessible_tenants = []
        if user.is_superuser:
            all_tenants = Tenant.objects.filter(is_deleted=False)
            for t in all_tenants:
                accessible_tenants.append({
                    "id": str(t.id),
                    "name": t.name,
                    "slug": t.slug,
                    "institution_type": t.institution_type,
                    "currency": t.currency,
                    "timezone": t.timezone,
                    "is_default": str(t.id) == str(tenant.id) if tenant else False,
                })
        else:
            for m in memberships:
                accessible_tenants.append({
                    "id": str(m.tenant.id),
                    "name": m.tenant.name,
                    "slug": m.tenant.slug,
                    "institution_type": m.tenant.institution_type,
                    "currency": m.tenant.currency,
                    "timezone": m.tenant.timezone,
                    "is_default": m.is_default,
                })

        return Response({
            "success": True,
            "data": {
                "user": UserSerializer(user).data,
                "active_tenant": {
                    "id": str(tenant.id) if tenant else None,
                    "name": tenant.name if tenant else None,
                    "slug": tenant.slug if tenant else None,
                    "institution_type": tenant.institution_type if tenant else "school",
                    "currency": tenant.currency if tenant else "USD",
                    "timezone": tenant.timezone if tenant else "UTC",
                } if tenant else None,
                "is_institution_superadmin": is_inst_super,
                "active_permissions": ["*"] if is_inst_super else (list(active_membership.get_permissions()) if active_membership else []),
                "memberships": MembershipSerializer(memberships, many=True).data,
                "accessible_tenants": accessible_tenants,
            }
        })


class SwitchTenantView(APIView):
    """
    Switches the active tenant context for the user by validating membership and setting it as default.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        tenant_id = request.data.get("tenant_id")
        if not tenant_id:
            return Response(
                {"success": False, "error": {"code": "MISSING_TENANT_ID", "message": "tenant_id is required."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        import uuid
        try:
            tenant_uuid = uuid.UUID(str(tenant_id).strip())
            membership_filter = {"tenant_id": tenant_uuid}
        except (ValueError, AttributeError):
            membership_filter = {"tenant__slug": str(tenant_id).strip().lower()}

        membership = Membership.objects.filter(
            user=request.user,
            status=Membership.STATUS_ACTIVE,
            is_deleted=False,
            **membership_filter,
        ).select_related("tenant").first()

        if not membership and not request.user.is_superuser:
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "CROSS_TENANT_FORBIDDEN",
                        "message": "You do not have an active membership with this organization.",
                    },
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Set as default membership
        Membership.objects.filter(user=request.user).update(is_default=False)
        if membership:
            membership.is_default = True
            membership.save(update_fields=["is_default"])

        return Response({
            "success": True,
            "message": f"Active organization switched to {membership.tenant.name if membership else 'selected tenant'}.",
            "data": {
                "active_tenant": {
                    "id": str(membership.tenant.id) if membership else str(tenant_id),
                    "name": membership.tenant.name if membership else "Tenant",
                    "slug": membership.tenant.slug if membership else "",
                }
            }
        })


class RoleViewSet(viewsets.ModelViewSet):
    """
    Role and Permissions management scoped to the active tenant.
    Institution Super Admins and authorized admins can create, view, and customize roles.
    """
    queryset = Role.objects.none()
    serializer_class = RoleSerializer
    permission_classes = [IsTenantMember]

    def get_queryset(self):
        from apps.accounts.permissions import get_or_resolve_tenant
        tenant = get_or_resolve_tenant(self.request)
        if getattr(self, "swagger_fake_view", False) or not tenant:
            return Role.objects.none()

        roles = Role.objects.filter(tenant=tenant, is_deleted=False)
        if not roles.exists():
            from apps.accounts.serializers import bootstrap_tenant_roles_and_permissions
            bootstrap_tenant_roles_and_permissions(tenant)
            roles = Role.objects.filter(tenant=tenant, is_deleted=False)

        system_roles = Role.objects.filter(tenant=None, is_system_role=True)
        return (roles | system_roles).distinct().order_by("name")

    def perform_create(self, serializer):
        from apps.accounts.permissions import get_or_resolve_tenant, is_user_institution_superadmin
        tenant = get_or_resolve_tenant(self.request)
        if not is_user_institution_superadmin(self.request.user, tenant):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Only Institution Super Admins can define new roles.")
        role = serializer.save(tenant=tenant)
        log_audit_event(
            action="CREATE",
            resource_type="Role",
            resource_id=str(role.id),
            actor=self.request.user,
            tenant=tenant,
            description=f"Created custom role '{role.name}' ({role.code}).",
            request=self.request,
        )


class InstitutionUserViewSet(viewsets.ModelViewSet):
    """
    Unified Institution User & Admin Management ViewSet.
    Allows Institution Super Admins and authorized Admins to list, create, edit, deactivate,
    reset passwords, and assign roles/permissions for all institutional users and staff.
    """
    queryset = Membership.objects.none()
    serializer_class = InstitutionUserSerializer
    permission_classes = [IsTenantMember]

    def get_queryset(self):
        from apps.accounts.permissions import get_or_resolve_tenant
        tenant = get_or_resolve_tenant(self.request)
        if getattr(self, "swagger_fake_view", False) or not tenant:
            return Membership.objects.none()

        # Ensure default roles exist for this tenant
        if not Role.objects.filter(tenant=tenant).exists():
            from apps.accounts.serializers import bootstrap_tenant_roles_and_permissions
            bootstrap_tenant_roles_and_permissions(tenant)

        qs = Membership.objects.filter(
            tenant=tenant,
            is_deleted=False,
        ).select_related("user", "tenant").prefetch_related(
            "membership_roles__role",
            "membership_roles__role__role_permissions__permission",
        )

        role = self.request.query_params.get("role")
        if role:
            qs = qs.filter(membership_roles__role__code=role)

        status_param = self.request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param)

        search = self.request.query_params.get("search")
        if search:
            from django.db.models import Q
            qs = qs.filter(
                Q(user__email__icontains=search) |
                Q(user__first_name__icontains=search) |
                Q(user__last_name__icontains=search)
            )

        return qs.order_by("-joined_at")

    def get_serializer_class(self):
        if self.action == "create":
            return InstitutionUserCreateSerializer
        elif self.action in ["update", "partial_update"]:
            return InstitutionUserUpdateSerializer
        return InstitutionUserSerializer

    def create(self, request, *args, **kwargs):
        from apps.accounts.permissions import get_or_resolve_tenant, is_user_institution_superadmin
        tenant = get_or_resolve_tenant(request)
        is_super = is_user_institution_superadmin(request.user, tenant)

        role_code = request.data.get("role_code", "faculty")
        is_admin_target = role_code in [Role.CODE_INSTITUTION_SUPER_ADMIN, Role.CODE_INSTITUTION_ADMIN, Role.CODE_SUPER_ADMIN]

        if is_admin_target and not is_super:
            return Response(
                {"success": False, "error": {"code": "FORBIDDEN", "message": "Only Institution Super Admins can create Admin accounts."}},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = InstitutionUserCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        membership = serializer.save()

        return Response({
            "success": True,
            "message": f"User account '{membership.user.email}' created successfully.",
            "data": InstitutionUserSerializer(membership).data,
        }, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        membership = self.get_object()
        from apps.accounts.permissions import get_or_resolve_tenant, is_user_institution_superadmin
        tenant = get_or_resolve_tenant(request)
        is_super = is_user_institution_superadmin(request.user, tenant)

        target_is_super = Role.objects.filter(
            membership_roles__membership=membership,
            code__in=[Role.CODE_INSTITUTION_SUPER_ADMIN, Role.CODE_SUPER_ADMIN],
        ).exists() or membership.user.is_superuser

        # Hierarchy protection: only Super Admin can edit Super Admin
        if target_is_super and not is_super:
            return Response(
                {"success": False, "error": {"code": "FORBIDDEN", "message": "You cannot modify an Institution Super Admin account."}},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = InstitutionUserUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        user = membership.user
        if "first_name" in data:
            user.first_name = data["first_name"]
        if "last_name" in data:
            user.last_name = data["last_name"]
        if "phone_number" in data:
            user.phone_number = data["phone_number"]
        user.save()

        if "status" in data:
            membership.status = data["status"]
            user.is_active = (data["status"] == Membership.STATUS_ACTIVE)
            user.save(update_fields=["is_active"])
            membership.save(update_fields=["status"])

        if "role_code" in data:
            new_role_code = data["role_code"]
            if new_role_code in [Role.CODE_INSTITUTION_SUPER_ADMIN, Role.CODE_SUPER_ADMIN] and not is_super:
                return Response(
                    {"success": False, "error": {"code": "FORBIDDEN", "message": "Only Super Admins can promote users to Super Admin."}},
                    status=status.HTTP_403_FORBIDDEN,
                )

            new_role = Role.objects.filter(tenant=tenant, code=new_role_code, is_deleted=False).first()
            if not new_role:
                new_role = Role.objects.filter(is_system_role=True, code=new_role_code).first()
            if not new_role:
                new_role = Role.objects.create(tenant=tenant, code=new_role_code, name=new_role_code.replace("_", " ").title())

            MembershipRole.objects.filter(membership=membership).delete()
            MembershipRole.objects.create(membership=membership, role=new_role)

            if "permissions" in data:
                for p_code in data["permissions"]:
                    p = Permission.objects.filter(code=p_code).first()
                    if p:
                        RolePermission.objects.get_or_create(role=new_role, permission=p)

        from apps.staff.models import Staff
        staff = Staff.objects.filter(user=user, tenant=tenant).first()
        if staff:
            if "designation" in data and data["designation"]:
                staff.designation = data["designation"]
            if "department_id" in data:
                staff.department_id = data["department_id"]
            staff.save()

        log_audit_event(
            action="UPDATE",
            resource_type="Membership",
            resource_id=str(membership.id),
            actor=request.user,
            tenant=tenant,
            description=f"Updated institutional user '{user.email}'.",
            changes=data,
            request=request,
        )

        return Response({
            "success": True,
            "message": f"User account '{user.email}' updated successfully.",
            "data": InstitutionUserSerializer(membership).data,
        })

    @action(detail=True, methods=["post"], url_path="toggle-status")
    def toggle_status(self, request, pk=None):
        """
        Activates or deactivates (suspends) an institutional user account.
        """
        membership = self.get_object()
        from apps.accounts.permissions import get_or_resolve_tenant, is_user_institution_superadmin
        tenant = get_or_resolve_tenant(request)
        is_super = is_user_institution_superadmin(request.user, tenant)

        target_is_super = Role.objects.filter(
            membership_roles__membership=membership,
            code__in=[Role.CODE_INSTITUTION_SUPER_ADMIN, Role.CODE_SUPER_ADMIN],
        ).exists() or membership.user.is_superuser

        if target_is_super and not is_super:
            return Response(
                {"success": False, "error": {"code": "FORBIDDEN", "message": "You cannot deactivate an Institution Super Admin."}},
                status=status.HTTP_403_FORBIDDEN,
            )

        if str(membership.user.id) == str(request.user.id):
            return Response(
                {"success": False, "error": {"code": "FORBIDDEN", "message": "You cannot deactivate your own account."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if membership.status == Membership.STATUS_ACTIVE:
            membership.status = Membership.STATUS_SUSPENDED
            membership.user.is_active = False
            action_desc = "deactivated/suspended"
        else:
            membership.status = Membership.STATUS_ACTIVE
            membership.user.is_active = True
            action_desc = "activated"

        membership.save(update_fields=["status"])
        membership.user.save(update_fields=["is_active"])

        # Also update staff status if present
        from apps.staff.models import Staff
        Staff.objects.filter(user=membership.user, tenant=tenant).update(
            status=Staff.STATUS_ACTIVE if membership.status == Membership.STATUS_ACTIVE else Staff.STATUS_TERMINATED
        )

        log_audit_event(
            action="UPDATE",
            resource_type="Membership",
            resource_id=str(membership.id),
            actor=request.user,
            tenant=tenant,
            description=f"Admin {action_desc} user account '{membership.user.email}'.",
            request=request,
        )

        return Response({
            "success": True,
            "message": f"User account '{membership.user.email}' is now {membership.status}.",
            "data": InstitutionUserSerializer(membership).data,
        })

    @action(detail=True, methods=["post"], url_path="reset-password")
    def reset_password(self, request, pk=None):
        """
        Allows Super Admin / authorized admin to reset user password.
        """
        membership = self.get_object()
        from apps.accounts.permissions import get_or_resolve_tenant, is_user_institution_superadmin
        tenant = get_or_resolve_tenant(request)
        is_super = is_user_institution_superadmin(request.user, tenant)

        target_is_super = Role.objects.filter(
            membership_roles__membership=membership,
            code__in=[Role.CODE_INSTITUTION_SUPER_ADMIN, Role.CODE_SUPER_ADMIN],
        ).exists() or membership.user.is_superuser

        if target_is_super and not is_super:
            return Response(
                {"success": False, "error": {"code": "FORBIDDEN", "message": "You cannot reset a Super Admin's password."}},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = InstitutionUserResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        membership.user.set_password(serializer.validated_data["new_password"])
        membership.user.save()

        log_audit_event(
            action="UPDATE",
            resource_type="User",
            resource_id=str(membership.user.id),
            actor=request.user,
            tenant=tenant,
            description=f"Admin reset password for user '{membership.user.email}'.",
            request=request,
        )

        return Response({
            "success": True,
            "message": f"Password for '{membership.user.email}' has been reset successfully.",
        })

    def destroy(self, request, *args, **kwargs):
        membership = self.get_object()
        from apps.accounts.permissions import get_or_resolve_tenant, is_user_institution_superadmin
        tenant = get_or_resolve_tenant(request)
        is_super = is_user_institution_superadmin(request.user, tenant)

        target_is_super = Role.objects.filter(
            membership_roles__membership=membership,
            code__in=[Role.CODE_INSTITUTION_SUPER_ADMIN, Role.CODE_SUPER_ADMIN],
        ).exists() or membership.user.is_superuser

        if target_is_super and not is_super:
            return Response(
                {"success": False, "error": {"code": "FORBIDDEN", "message": "You cannot remove an Institution Super Admin."}},
                status=status.HTTP_403_FORBIDDEN,
            )

        if str(membership.user.id) == str(request.user.id):
            return Response(
                {"success": False, "error": {"code": "FORBIDDEN", "message": "You cannot delete your own membership."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        email = membership.user.email
        membership.delete()

        log_audit_event(
            action="DELETE",
            resource_type="Membership",
            resource_id=str(membership.id),
            actor=request.user,
            tenant=tenant,
            description=f"Removed user '{email}' from institution '{tenant.name}'.",
            request=request,
        )

        return Response({
            "success": True,
            "message": f"User '{email}' removed from organization.",
        })


class MembershipViewSet(viewsets.ModelViewSet):
    """
    Manage user memberships and role assignments within the active tenant.
    """
    queryset = Membership.objects.none()
    serializer_class = MembershipSerializer
    permission_classes = [IsInstitutionAdmin]

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        if getattr(self, "swagger_fake_view", False) or not tenant:
            return Membership.objects.none()
        return Membership.objects.filter(
            tenant=tenant,
            is_deleted=False,
        ).select_related("user", "tenant")


class PermissionListView(generics.ListAPIView):
    """
    Catalog of all available permissions in the system.
    """
    queryset = Permission.objects.all()
    serializer_class = PermissionSerializer
    permission_classes = [IsTenantMember]

