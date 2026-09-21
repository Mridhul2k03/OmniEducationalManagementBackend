from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from apps.tenants.models import Tenant
from apps.tenants.serializers import TenantSerializer, TenantDetailSerializer
from apps.accounts.permissions import IsSuperAdmin, IsInstitutionAdmin
from apps.audit.services import log_audit_event


class TenantViewSet(viewsets.ModelViewSet):
    """
    Tenant management.
    List/Retrieve: accessible to members for their tenant, or superadmins for all.
    Update: accessible to Institution Admins and Superadmins.
    Create/Delete: restricted to Superadmins or onboarding flow.
    """
    queryset = Tenant.objects.all()
    lookup_field = "id"

    def get_serializer_class(self):
        if self.action in ["retrieve", "update", "partial_update"]:
            return TenantDetailSerializer
        return TenantSerializer

    def get_permissions(self):
        if self.action in ["create", "destroy"]:
            return [IsSuperAdmin()]
        elif self.action in ["update", "partial_update"]:
            return [IsInstitutionAdmin()]
        elif self.action == "list":
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        if not self.request.user or not self.request.user.is_authenticated:
            return Tenant.objects.filter(is_deleted=False, status=Tenant.STATUS_ACTIVE)
        if self.request.user.is_superuser:
            return Tenant.objects.filter(is_deleted=False)
        # Return only tenants where the user has an active membership
        return Tenant.objects.filter(
            memberships__user=self.request.user,
            memberships__status="active",
            is_deleted=False,
        ).distinct()

    def perform_update(self, serializer):
        instance = serializer.save()
        log_audit_event(
            action="UPDATE",
            resource_type="Tenant",
            resource_id=str(instance.id),
            tenant=instance,
            actor=self.request.user,
            changes=serializer.validated_data,
            description=f"Tenant '{instance.name}' configuration updated.",
            request=self.request,
        )

    # ── Shared plan catalog (single source of truth) ──
    PLAN_CATALOG = {
        "starter": {
            "id": "starter",
            "name": "Starter Academy",
            "monthly_price": 49,
            "annual_price": 490,
            "tagline": "Essential SIS foundation for growing primary & coaching centers",
            "features": {
                "students_limit": 250,
                "staff_limit": 25,
                "ai_tutor": False,
                "exams": False,
                "lms": False,
                "finance_advanced": False,
                "audit_logs": False,
                "multi_campus": False,
                "priority_support": False,
            },
            "highlights": [
                "Up to 250 Learners & 25 Staff",
                "Core SIS Student & Staff Profiles",
                "Timetable & Period Schedules",
                "Daily Attendance Management",
                "Basic Tuition Billing & Invoices",
            ],
        },
        "professional": {
            "id": "professional",
            "name": "Professional Campus",
            "monthly_price": 149,
            "annual_price": 1490,
            "tagline": "Full-spectrum academic suite with AI Tutor for modern institutions",
            "features": {
                "students_limit": 2500,
                "staff_limit": 150,
                "ai_tutor": True,
                "exams": True,
                "lms": True,
                "finance_advanced": True,
                "audit_logs": False,
                "multi_campus": False,
                "priority_support": True,
            },
            "highlights": [
                "Up to 2,500 Learners & 150 Faculty",
                "Gemini AI Tutor & Study Plan Generator",
                "Examinations, Gradebook & Report Cards",
                "LMS Course Materials & Lesson Plans",
                "Advanced Multi-term Tuition Billing",
                "Priority Institutional Support",
            ],
            "is_popular": True,
        },
        "enterprise": {
            "id": "enterprise",
            "name": "Enterprise University",
            "monthly_price": 399,
            "annual_price": 3990,
            "tagline": "Unrestricted scale, compliance audit logs & multi-campus federation",
            "features": {
                "students_limit": 999999,
                "staff_limit": 999999,
                "ai_tutor": True,
                "exams": True,
                "lms": True,
                "finance_advanced": True,
                "audit_logs": True,
                "multi_campus": True,
                "priority_support": True,
            },
            "highlights": [
                "Unlimited Students, Faculty & Campuses",
                "Gemini AI Tutor (Unlimited Quota)",
                "Full Forensic Security Audit Logs",
                "Custom Institutional Domains & SSO",
                "Dedicated Technical Account Manager",
                "SLA 99.9% Uptime Guarantee",
            ],
        },
    }

    @staticmethod
    def _normalize_plan_id(raw):
        """Normalize plan id to lowercase key matching PLAN_CATALOG."""
        if not raw:
            return "starter"
        normalized = raw.strip().lower()
        if normalized in ("starter", "professional", "enterprise"):
            return normalized
        # Also handle Title-case stored in older DB records
        title = raw.strip().title()
        mapping = {"Starter": "starter", "Professional": "professional", "Enterprise": "enterprise"}
        return mapping.get(title, "starter")

    @action(detail=False, methods=["get"], permission_classes=[permissions.IsAuthenticated], url_path="current-plan")
    def current_plan(self, request):
        """
        Returns active SaaS subscription plan details, usage quotas, and feature flags.
        Response shape matches frontend CurrentPlanResponse interface.
        """
        from apps.accounts.permissions import get_or_resolve_tenant
        from apps.students.models import Student
        from apps.staff.models import Staff

        tenant = getattr(request, "tenant", None) or get_or_resolve_tenant(request)
        if not tenant:
            return Response(
                {"success": False, "error": {"code": "NO_ACTIVE_TENANT", "message": "No active tenant selected."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        plan_id = self._normalize_plan_id(tenant.subscription_reference)
        active_plan = self.PLAN_CATALOG[plan_id]
        active_students = Student.objects.filter(tenant=tenant, is_deleted=False).count()
        active_staff = Staff.objects.filter(tenant=tenant, is_deleted=False).count()

        return Response({
            "success": True,
            "data": {
                "current_plan_id": plan_id,
                "current_plan": active_plan,
                "available_plans": self.PLAN_CATALOG,
                "features": active_plan["features"],
                "usage": {
                    "students": active_students,
                    "students_limit": active_plan["features"]["students_limit"],
                    "students_pct": min(100.0, round((active_students / max(1, active_plan["features"]["students_limit"])) * 100, 1)),
                    "staff": active_staff,
                    "staff_limit": active_plan["features"]["staff_limit"],
                    "staff_pct": min(100.0, round((active_staff / max(1, active_plan["features"]["staff_limit"])) * 100, 1)),
                }
            }
        })

    @action(detail=False, methods=["post"], permission_classes=[permissions.IsAuthenticated], url_path="upgrade-plan")
    def upgrade_plan(self, request):
        """
        Upgrades or switches the tenant's subscription plan.
        Accepts plan_id in any case (e.g. "starter", "Starter", "STARTER").
        """
        from apps.accounts.permissions import get_or_resolve_tenant
        tenant = getattr(request, "tenant", None) or get_or_resolve_tenant(request)
        if not tenant:
            return Response({"success": False, "error": {"code": "NO_ACTIVE_TENANT", "message": "No active tenant."}}, status=400)

        raw_plan = request.data.get("plan_id", "")
        new_plan = self._normalize_plan_id(raw_plan)
        if new_plan not in self.PLAN_CATALOG:
            return Response({"success": False, "error": {"code": "INVALID_PLAN", "message": "Plan must be starter, professional, or enterprise."}}, status=400)

        old_plan = self._normalize_plan_id(tenant.subscription_reference)
        # Store lowercase in DB for consistency
        tenant.subscription_reference = new_plan
        tenant.save(update_fields=["subscription_reference"])

        log_audit_event(
            action="UPDATE",
            resource_type="SubscriptionPlan",
            resource_id=str(tenant.id),
            tenant=tenant,
            actor=request.user,
            description=f"Upgraded plan from {old_plan} to {new_plan}",
            changes={"old_plan": old_plan, "new_plan": new_plan},
            request=request,
        )

        return Response({
            "success": True,
            "message": f"Successfully updated subscription to {self.PLAN_CATALOG[new_plan]['name']}.",
            "data": {"plan_id": new_plan}
        })
