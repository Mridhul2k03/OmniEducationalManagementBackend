"""
Views for Platform SuperAdmin Console.
Exposes top-level administrative operations over Users, Organizations (Tenants), Memberships, and Global Analytics.
"""
from decimal import Decimal
from django.db.models import Sum, Count, Q
from rest_framework import viewsets, permissions, status, filters
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from apps.accounts.models import User, Membership, Role, MembershipRole
from apps.accounts.permissions import IsSuperAdmin
from apps.tenants.models import Tenant
from apps.students.models import Student
from apps.staff.models import Staff
from apps.finance.models import Invoice, Payment
from apps.audit.models import AuditLog
from apps.audit.services import log_audit_event

from apps.platform_admin.serializers import (
    PlatformUserSerializer,
    PlatformUserCreateSerializer,
    PlatformUserUpdateSerializer,
    PlatformPasswordResetSerializer,
    PlatformAssignTenantSerializer,
    PlatformTenantAdminSerializer,
    PlatformTenantCreateSerializer,
    PlatformTenantUpdateSerializer,
    PlatformAuditLogSerializer,
)


class PlatformUserViewSet(viewsets.ModelViewSet):
    """
    SuperAdmin User Control Center.
    Lists, creates, updates, and manages users across all tenant organizations.
    """
    permission_classes = [IsSuperAdmin]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["email", "first_name", "last_name", "phone_number"]
    ordering_fields = ["created_at", "email", "first_name", "is_active"]
    ordering = ["-created_at"]

    def get_queryset(self):
        qs = User.objects.all().prefetch_related(
            "memberships__tenant",
            "memberships__membership_roles__role",
        )
        
        # Optional filters
        is_active = self.request.query_params.get("is_active")
        if is_active is not None:
            qs = qs.filter(is_active=is_active.lower() == "true")

        is_staff = self.request.query_params.get("is_staff")
        if is_staff is not None:
            qs = qs.filter(is_staff=is_staff.lower() == "true")

        tenant_id = self.request.query_params.get("tenant_id")
        if tenant_id:
            qs = qs.filter(memberships__tenant_id=tenant_id, memberships__is_deleted=False)

        role = self.request.query_params.get("role")
        if role:
            qs = qs.filter(memberships__membership_roles__role__code=role, memberships__is_deleted=False)

        return qs.distinct()

    def get_serializer_class(self):
        if self.action == "create":
            return PlatformUserCreateSerializer
        elif self.action in ["update", "partial_update"]:
            return PlatformUserUpdateSerializer
        return PlatformUserSerializer

    def perform_create(self, serializer):
        user = serializer.save()
        log_audit_event(
            action="CREATE",
            resource_type="User",
            resource_id=str(user.id),
            actor=self.request.user,
            description=f"SuperAdmin created user account '{user.email}'.",
            request=self.request,
        )

    def perform_update(self, serializer):
        user = serializer.save()
        log_audit_event(
            action="UPDATE",
            resource_type="User",
            resource_id=str(user.id),
            actor=self.request.user,
            changes=serializer.validated_data,
            description=f"SuperAdmin updated user account '{user.email}'.",
            request=self.request,
        )

    def perform_destroy(self, instance):
        email = instance.email
        uid = str(instance.id)
        instance.delete()
        log_audit_event(
            action="DELETE",
            resource_type="User",
            resource_id=uid,
            actor=self.request.user,
            description=f"SuperAdmin deleted user account '{email}'.",
            request=self.request,
        )

    @action(detail=True, methods=["post"], url_path="reset-password")
    def reset_password(self, request, pk=None):
        """
        Allows SuperAdmin to set a new password for any user account.
        """
        user = self.get_object()
        serializer = PlatformPasswordResetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        new_password = serializer.validated_data["new_password"]
        user.set_password(new_password)
        user.save()

        log_audit_event(
            action="UPDATE",
            resource_type="User",
            resource_id=str(user.id),
            actor=request.user,
            description=f"SuperAdmin manually reset password for user '{user.email}'.",
            request=request,
        )

        return Response({
            "success": True,
            "message": f"Password for {user.email} has been reset successfully.",
        })

    @action(detail=True, methods=["post"], url_path="toggle-status")
    def toggle_status(self, request, pk=None):
        """
        Toggles active/suspended state of a user account.
        """
        user = self.get_object()
        user.is_active = not user.is_active
        user.save(update_fields=["is_active"])

        action_word = "activated" if user.is_active else "suspended"
        log_audit_event(
            action="UPDATE",
            resource_type="User",
            resource_id=str(user.id),
            actor=request.user,
            description=f"SuperAdmin {action_word} user account '{user.email}'.",
            request=request,
        )

        return Response({
            "success": True,
            "message": f"User account {user.email} is now {action_word}.",
            "data": {"is_active": user.is_active}
        })

    @action(detail=True, methods=["post"], url_path="assign-tenant")
    def assign_tenant(self, request, pk=None):
        """
        Assigns or updates a user's membership and role in a specified tenant organization.
        """
        user = self.get_object()
        serializer = PlatformAssignTenantSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        tenant_id = serializer.validated_data["tenant_id"]
        role_code = serializer.validated_data.get("role_code", "faculty")
        is_default = serializer.validated_data.get("is_default", False)

        tenant = Tenant.objects.filter(id=tenant_id, is_deleted=False).first()
        if not tenant:
            return Response(
                {"success": False, "error": {"code": "NOT_FOUND", "message": "Tenant organization not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )

        if is_default:
            Membership.objects.filter(user=user).update(is_default=False)

        membership, _ = Membership.objects.get_or_create(
            user=user,
            tenant=tenant,
            defaults={"status": Membership.STATUS_ACTIVE, "is_default": is_default},
        )
        if is_default:
            membership.is_default = True
            membership.save(update_fields=["is_default"])

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

        log_audit_event(
            action="UPDATE",
            resource_type="Membership",
            resource_id=str(membership.id),
            actor=request.user,
            tenant=tenant,
            description=f"SuperAdmin assigned user '{user.email}' to tenant '{tenant.name}' with role '{role_code}'.",
            request=request,
        )

        return Response({
            "success": True,
            "message": f"User {user.email} assigned to {tenant.name} as {role_code}.",
            "data": PlatformUserSerializer(user).data,
        })


class PlatformTenantViewSet(viewsets.ModelViewSet):
    """
    SuperAdmin Tenant Management.
    Lists, provisions, updates, and controls all institutional client tenants.
    """
    permission_classes = [IsSuperAdmin]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "slug", "legal_name", "contact_email"]
    ordering_fields = ["created_at", "name", "status"]
    ordering = ["-created_at"]
    queryset = Tenant.objects.all().order_by("-created_at")

    def get_serializer_class(self):
        if self.action == "create":
            return PlatformTenantCreateSerializer
        elif self.action in ["update", "partial_update"]:
            return PlatformTenantUpdateSerializer
        return PlatformTenantAdminSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tenant = serializer.save()
        log_audit_event(
            action="CREATE",
            resource_type="Tenant",
            resource_id=str(tenant.id),
            tenant=tenant,
            actor=request.user,
            description=f"SuperAdmin provisioned new institution tenant '{tenant.name}' ({tenant.slug}).",
            request=request,
        )
        return Response(
            PlatformTenantAdminSerializer(tenant).data,
            status=status.HTTP_201_CREATED,
        )

    def perform_update(self, serializer):
        tenant = serializer.save()
        log_audit_event(
            action="UPDATE",
            resource_type="Tenant",
            resource_id=str(tenant.id),
            tenant=tenant,
            actor=self.request.user,
            changes=serializer.validated_data,
            description=f"SuperAdmin updated institution tenant '{tenant.name}'.",
            request=self.request,
        )

    @action(detail=True, methods=["post"], url_path="toggle-status")
    def toggle_status(self, request, pk=None):
        """
        Toggles tenant between Active and Suspended states.
        """
        tenant = self.get_object()
        new_status = Tenant.STATUS_SUSPENDED if tenant.status == Tenant.STATUS_ACTIVE else Tenant.STATUS_ACTIVE
        tenant.status = new_status
        tenant.save(update_fields=["status"])

        log_audit_event(
            action="UPDATE",
            resource_type="Tenant",
            resource_id=str(tenant.id),
            tenant=tenant,
            actor=request.user,
            description=f"SuperAdmin set tenant '{tenant.name}' status to '{new_status}'.",
            request=request,
        )

        return Response({
            "success": True,
            "message": f"Tenant '{tenant.name}' is now {new_status}.",
            "data": {"status": tenant.status}
        })


class PlatformStatsView(APIView):
    """
    SuperAdmin Executive Dashboard Statistics.
    Returns global SaaS metrics across all tenants and users.
    """
    permission_classes = [IsSuperAdmin]

    def get(self, request):
        total_tenants = Tenant.objects.filter(is_deleted=False).count()
        active_tenants = Tenant.objects.filter(is_deleted=False, status=Tenant.STATUS_ACTIVE).count()
        suspended_tenants = Tenant.objects.filter(is_deleted=False, status=Tenant.STATUS_SUSPENDED).count()

        total_users = User.objects.count()
        active_users = User.objects.filter(is_active=True).count()
        superadmins = User.objects.filter(is_superuser=True).count()
        staff_users = User.objects.filter(is_staff=True).count()

        total_students = Student.objects.filter(is_deleted=False).count()
        total_staff = Staff.objects.filter(is_deleted=False).count()

        invoices_agg = Invoice.objects.filter(is_deleted=False).aggregate(
            total_billed=Sum("total_amount"),
            total_collected=Sum("paid_amount"),
            count=Count("id"),
        )
        total_billed = float(invoices_agg["total_billed"] or 0)
        total_collected = float(invoices_agg["total_collected"] or 0)

        # Recent tenants
        recent_tenants = PlatformTenantAdminSerializer(
            Tenant.objects.filter(is_deleted=False).order_by("-created_at")[:5],
            many=True,
        ).data

        # Recent users
        recent_users = PlatformUserSerializer(
            User.objects.order_by("-created_at")[:5],
            many=True,
        ).data

        return Response({
            "success": True,
            "data": {
                "tenants": {
                    "total": total_tenants,
                    "active": active_tenants,
                    "suspended": suspended_tenants,
                },
                "users": {
                    "total": total_users,
                    "active": active_users,
                    "superadmins": superadmins,
                    "staff": staff_users,
                },
                "academics": {
                    "total_students": total_students,
                    "total_staff": total_staff,
                },
                "finance": {
                    "total_invoiced": total_billed,
                    "total_collected": total_collected,
                    "total_invoices": invoices_agg["count"] or 0,
                    "collection_rate": round((total_collected / total_billed * 100), 1) if total_billed > 0 else 0,
                },
                "recent_tenants": recent_tenants,
                "recent_users": recent_users,
            }
        })


class PlatformAuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    SuperAdmin Platform Audit Log Viewer.
    Provides compliance and security tracking across all tenants.
    """
    permission_classes = [IsSuperAdmin]
    serializer_class = PlatformAuditLogSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["description", "resource_type", "resource_id", "actor__email", "actor__first_name", "actor__last_name"]
    ordering_fields = ["created_at", "action", "resource_type"]
    ordering = ["-created_at"]

    def get_queryset(self):
        qs = AuditLog.objects.all().select_related("tenant", "actor")
        
        tenant_id = self.request.query_params.get("tenant_id")
        if tenant_id:
            qs = qs.filter(tenant_id=tenant_id)

        action_filter = self.request.query_params.get("action")
        if action_filter:
            qs = qs.filter(action=action_filter.upper())

        return qs
