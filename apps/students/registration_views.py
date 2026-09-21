"""
Learner Self-Registration, Separate Student Authentication, Re-Request Cooldown,
and Administrative Verification Workflow views.
"""
from datetime import timedelta
from django.db import transaction, models
from django.utils import timezone
from django.conf import settings
from rest_framework import views, viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User, Membership, Role, MembershipRole
from apps.accounts.views import set_auth_cookies
from apps.accounts.serializers import UserSerializer
from apps.accounts.permissions import get_or_resolve_tenant, IsInstitutionAdmin
from apps.tenants.models import Tenant
from apps.students.models import Student, StudentRegistrationRequest
from apps.students.serializers import (
    StudentRegistrationRequestSerializer,
    StudentSelfRegisterSerializer,
)
from apps.audit.services import log_audit_event


class StudentRegisterView(views.APIView):
    """
    Public endpoint: Allows prospective/enrolled students to submit a self-registration
    and verification request to an educational institution.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = StudentSelfRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        tenant_id_raw = str(data["tenant_id"]).strip()
        tenant = None
        try:
            import uuid
            tenant_uuid = uuid.UUID(tenant_id_raw)
            tenant = Tenant.objects.filter(id=tenant_uuid, is_deleted=False).first()
        except (ValueError, AttributeError):
            tenant = Tenant.objects.filter(slug__iexact=tenant_id_raw, is_deleted=False).first()

        if not tenant:
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "TENANT_NOT_FOUND",
                        "message": "Selected educational institution could not be located or is inactive.",
                    },
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        email = data["email"].strip().lower()
        admission_number = data["admission_number"].strip()

        # 1. Check permanent rejection blacklist in this tenant
        perm_rejected = StudentRegistrationRequest.objects.filter(
            tenant=tenant,
            status=StudentRegistrationRequest.STATUS_PERMANENTLY_REJECTED,
        ).filter(
            models.Q(email__iexact=email) | models.Q(admission_number__iexact=admission_number)
        ).first()

        if perm_rejected:
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "PERMANENTLY_REJECTED",
                        "message": "This registration request has been permanently rejected by the institution administration.",
                        "details": perm_rejected.rejection_reason or "Applicant identity permanently rejected.",
                    },
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # 2. Check if active student already exists in this tenant
        existing_student = Student.objects.filter(tenant=tenant).filter(
            models.Q(user__email__iexact=email) | models.Q(admission_number__iexact=admission_number)
        ).first()
        if existing_student:
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "ALREADY_REGISTERED",
                        "message": f"A student account with this email or admission number '{admission_number}' is already enrolled. Please sign in.",
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 3. Check existing request for this email + tenant
        existing_request = StudentRegistrationRequest.objects.filter(
            tenant=tenant,
            email__iexact=email,
        ).order_by("-created_at").first()

        gap_hours = getattr(settings, "STUDENT_REGISTRATION_REREQUEST_GAP_HOURS", 24)

        if existing_request:
            if existing_request.status == StudentRegistrationRequest.STATUS_PENDING:
                return Response(
                    {
                        "success": False,
                        "error": {
                            "code": "REQUEST_PENDING",
                            "message": "A registration request is already under review by the institution administration.",
                            "requested_at": existing_request.last_requested_at.isoformat() if existing_request.last_requested_at else None,
                        },
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            elif existing_request.status == StudentRegistrationRequest.STATUS_REJECTED:
                can_re, remaining, msg = existing_request.can_re_request(gap_hours=gap_hours)
                if not can_re:
                    return Response(
                        {
                            "success": False,
                            "error": {
                                "code": "COOLDOWN_ACTIVE",
                                "message": msg or f"Cooldown period active ({gap_hours} hours).",
                                "rejection_reason": existing_request.rejection_reason,
                                "hours_remaining": round(remaining.total_seconds() / 3600, 1) if remaining else 0,
                                "eligible_re_request_at": (existing_request.last_requested_at + timedelta(hours=gap_hours)).isoformat(),
                            },
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                # Cooldown period has elapsed: update and re-submit as pending
                with transaction.atomic():
                    existing_request.first_name = data["first_name"]
                    existing_request.last_name = data["last_name"]
                    existing_request.phone_number = data.get("phone_number", "")
                    existing_request.admission_number = admission_number
                    existing_request.grade_or_program = data.get("grade_or_program", "")
                    existing_request.gender = data.get("gender", Student.GENDER_FEMALE)
                    existing_request.date_of_birth = data.get("date_of_birth")
                    existing_request.notes = data.get("notes", "")
                    existing_request.status = StudentRegistrationRequest.STATUS_PENDING
                    existing_request.last_requested_at = timezone.now()
                    existing_request.re_request_count += 1
                    existing_request.rejection_reason = ""
                    existing_request.save()

                    if existing_request.user:
                        existing_request.user.set_password(data["password"])
                        existing_request.user.save()

                return Response(
                    {
                        "success": True,
                        "message": "Your verification request has been re-submitted successfully and is pending administrative review.",
                        "data": StudentRegistrationRequestSerializer(existing_request).data,
                    },
                    status=status.HTTP_200_OK,
                )

        # 4. Fresh registration: provision inactive user and pending request
        with transaction.atomic():
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    "first_name": data["first_name"],
                    "last_name": data["last_name"],
                    "phone_number": data.get("phone_number", ""),
                    "is_active": False,
                },
            )
            user.set_password(data["password"])
            user.is_active = False
            user.save()

            reg_req = StudentRegistrationRequest.objects.create(
                tenant=tenant,
                user=user,
                email=email,
                first_name=data["first_name"],
                last_name=data["last_name"],
                phone_number=data.get("phone_number", ""),
                admission_number=admission_number,
                grade_or_program=data.get("grade_or_program", ""),
                gender=data.get("gender", Student.GENDER_FEMALE),
                date_of_birth=data.get("date_of_birth"),
                notes=data.get("notes", ""),
                status=StudentRegistrationRequest.STATUS_PENDING,
            )

        return Response(
            {
                "success": True,
                "message": "Student registration submitted successfully. Your account is now pending administrative verification and approval.",
                "data": StudentRegistrationRequestSerializer(reg_req).data,
            },
            status=status.HTTP_201_CREATED,
        )


class StudentLoginView(views.APIView):
    """
    Public endpoint: Dedicated login portal for students.
    Validates credentials and delivers helpful verification lifecycle messages
    (Pending, Rejected with cooldown, or Permanently Rejected).
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = str(request.data.get("email", "")).strip().lower()
        password = str(request.data.get("password", ""))

        if not email or not password:
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "MISSING_CREDENTIALS",
                        "message": "Please provide both institutional email and password.",
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = User.objects.filter(email__iexact=email).first()
        if not user or not user.check_password(password):
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "INVALID_CREDENTIALS",
                        "message": "Invalid institutional email or password. Please verify your credentials.",
                    },
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Resolve optional target tenant parameter (body param or header)
        tenant_param = (
            request.data.get("tenant_id")
            or request.data.get("institution")
            or request.headers.get("X-Tenant-ID")
        )

        target_tenant = None
        if tenant_param:
            import uuid
            try:
                val_uuid = uuid.UUID(str(tenant_param))
                target_tenant = Tenant.objects.filter(id=val_uuid).first()
            except (ValueError, TypeError, AttributeError):
                target_tenant = Tenant.objects.filter(slug__iexact=str(tenant_param)).first()

        req = None
        if target_tenant:
            req = StudentRegistrationRequest.objects.filter(
                email__iexact=email, tenant=target_tenant
            ).order_by("-created_at").first()

        # If no tenant requested or no request found for that specific tenant:
        if not req:
            # Prioritize an approved registration request for an active user
            approved_req = StudentRegistrationRequest.objects.filter(
                email__iexact=email, status=StudentRegistrationRequest.STATUS_APPROVED
            ).order_by("-reviewed_at", "-created_at").first()

            if approved_req and user.is_active:
                req = approved_req
            else:
                req = StudentRegistrationRequest.objects.filter(email__iexact=email).order_by("-created_at").first()

        gap_hours = getattr(settings, "STUDENT_REGISTRATION_REREQUEST_GAP_HOURS", 24)

        if req:
            if req.status == StudentRegistrationRequest.STATUS_PERMANENTLY_REJECTED:
                return Response(
                    {
                        "success": False,
                        "status": "permanently_rejected",
                        "error": {
                            "code": "PERMANENTLY_REJECTED",
                            "message": "Your registration request has been permanently rejected by the institution administration.",
                            "rejection_reason": req.rejection_reason or "False or unverified applicant credentials.",
                        },
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
            elif req.status == StudentRegistrationRequest.STATUS_REJECTED:
                can_re, remaining, msg = req.can_re_request(gap_hours=gap_hours)
                eligible_at = (req.last_requested_at + timedelta(hours=gap_hours)).isoformat() if req.last_requested_at else None
                return Response(
                    {
                        "success": False,
                        "status": "rejected",
                        "error": {
                            "code": "REQUEST_REJECTED",
                            "message": "Your registration request was not approved.",
                            "rejection_reason": req.rejection_reason or "Institutional details could not be verified.",
                            "can_re_request": can_re,
                            "re_request_gap_hours": gap_hours,
                            "hours_remaining": round(remaining.total_seconds() / 3600, 1) if remaining else 0,
                            "eligible_re_request_at": eligible_at,
                            "tenant_id": str(req.tenant_id) if req.tenant_id else None,
                        },
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
            elif (req.status == StudentRegistrationRequest.STATUS_PENDING or not user.is_active) and req.status != StudentRegistrationRequest.STATUS_APPROVED:
                return Response(
                    {
                        "success": False,
                        "status": "pending",
                        "error": {
                            "code": "PENDING_APPROVAL",
                            "message": "Your registration request is currently under review by the institution administration.",
                            "requested_at": req.last_requested_at.isoformat() if req.last_requested_at else None,
                            "admission_number": req.admission_number,
                            "institution_name": req.tenant.name if req.tenant else "",
                        },
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

        if not user.is_active:
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "ACCOUNT_INACTIVE",
                        "message": "Your student account is currently inactive. Please contact your institution administrator.",
                    },
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Authenticated & Approved: Issue JWT Token Pair & Cookies
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)

        # Resolve active membership and student record
        membership = None
        if req and req.tenant:
            membership = Membership.objects.filter(
                user=user,
                tenant=req.tenant,
                status=Membership.STATUS_ACTIVE,
                is_deleted=False,
            ).select_related("tenant").first()

        if not membership and target_tenant:
            membership = Membership.objects.filter(
                user=user,
                tenant=target_tenant,
                status=Membership.STATUS_ACTIVE,
                is_deleted=False,
            ).select_related("tenant").first()

        if not membership:
            membership = Membership.objects.filter(
                user=user,
                status=Membership.STATUS_ACTIVE,
                is_deleted=False,
            ).select_related("tenant").first()

        student_obj = None
        if membership and membership.tenant:
            student_obj = Student.objects.filter(user=user, tenant=membership.tenant, is_deleted=False).first()
        if not student_obj:
            student_obj = Student.objects.filter(user=user, is_deleted=False).first()

        tenant_data = None
        if membership and membership.tenant:
            t = membership.tenant
            tenant_data = {
                "id": str(t.id),
                "name": t.name,
                "slug": t.slug,
                "institution_type": t.institution_type,
                "currency": t.currency,
                "timezone": t.timezone,
            }

        response_data = {
            "success": True,
            "access": access_token,
            "refresh": refresh_token,
            "role": "student",
            "profile_type": "student",
            "user": UserSerializer(user).data,
            "student_profile": {
                "id": str(student_obj.id) if student_obj else None,
                "admission_number": student_obj.admission_number if student_obj else (req.admission_number if req else ""),
                "full_name": student_obj.full_name if student_obj else user.full_name,
                "status": student_obj.status if student_obj else "admitted",
            } if (student_obj or req) else None,
            "active_tenant": tenant_data,
        }

        response = Response(response_data, status=status.HTTP_200_OK)
        set_auth_cookies(response, access_token=access_token, refresh_token=refresh_token)
        return response


class StudentReRequestView(views.APIView):
    """
    Public endpoint: Allows a rejected student to re-request verification
    after the configurable cooldown period has passed.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = str(request.data.get("email", "")).strip().lower()
        tenant_id_raw = str(request.data.get("tenant_id", "")).strip()
        notes = str(request.data.get("notes", "")).strip()

        if not email:
            return Response(
                {"success": False, "error": {"message": "Email is required to re-request verification."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        query = StudentRegistrationRequest.objects.filter(email__iexact=email)
        if tenant_id_raw:
            try:
                import uuid
                u = uuid.UUID(tenant_id_raw)
                query = query.filter(models.Q(tenant_id=u) | models.Q(tenant__slug__iexact=tenant_id_raw))
            except (ValueError, AttributeError):
                query = query.filter(tenant__slug__iexact=tenant_id_raw)

        req = query.order_by("-created_at").first()
        if not req:
            return Response(
                {"success": False, "error": {"message": "No registration request found for this email."}},
                status=status.HTTP_404_NOT_FOUND,
            )

        if req.status == StudentRegistrationRequest.STATUS_PERMANENTLY_REJECTED:
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "PERMANENTLY_REJECTED",
                        "message": "This registration has been permanently rejected. Re-requests are not permitted.",
                    },
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        if req.status == StudentRegistrationRequest.STATUS_APPROVED:
            return Response(
                {"success": False, "error": {"message": "Your account has already been approved. Please sign in."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        gap_hours = getattr(settings, "STUDENT_REGISTRATION_REREQUEST_GAP_HOURS", 24)
        can_re, remaining, msg = req.can_re_request(gap_hours=gap_hours)

        if not can_re:
            eligible_at = (req.last_requested_at + timedelta(hours=gap_hours)).isoformat() if req.last_requested_at else None
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "COOLDOWN_ACTIVE",
                        "message": msg or f"Cooldown period active ({gap_hours} hours).",
                        "hours_remaining": round(remaining.total_seconds() / 3600, 1) if remaining else 0,
                        "eligible_re_request_at": eligible_at,
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        req.status = StudentRegistrationRequest.STATUS_PENDING
        req.last_requested_at = timezone.now()
        req.re_request_count += 1
        req.rejection_reason = ""
        if notes:
            req.notes = notes
        req.save()

        return Response(
            {
                "success": True,
                "message": "Verification re-request submitted successfully. An administrator will review your application.",
                "data": StudentRegistrationRequestSerializer(req).data,
            },
            status=status.HTTP_200_OK,
        )


class StudentCheckStatusView(views.APIView):
    """
    Public endpoint: Allows students to check their request status using email and institution.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = str(request.data.get("email", "")).strip().lower()
        tenant_param = (
            request.data.get("tenant_id")
            or request.data.get("institution")
            or request.headers.get("X-Tenant-ID")
        )

        if not email:
            return Response(
                {"success": False, "error": {"message": "Email is required to check status."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        target_tenant = None
        if tenant_param:
            import uuid
            try:
                val_uuid = uuid.UUID(str(tenant_param))
                target_tenant = Tenant.objects.filter(id=val_uuid).first()
            except (ValueError, TypeError, AttributeError):
                target_tenant = Tenant.objects.filter(slug__iexact=str(tenant_param)).first()

        req = None
        if target_tenant:
            req = StudentRegistrationRequest.objects.filter(
                email__iexact=email, tenant=target_tenant
            ).order_by("-created_at").first()

        if not req:
            approved_req = StudentRegistrationRequest.objects.filter(
                email__iexact=email, status=StudentRegistrationRequest.STATUS_APPROVED
            ).order_by("-reviewed_at", "-created_at").first()
            req = approved_req or StudentRegistrationRequest.objects.filter(email__iexact=email).order_by("-created_at").first()

        if not req:
            return Response(
                {"success": False, "error": {"message": "No registration request found for this email."}},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            {
                "success": True,
                "data": StudentRegistrationRequestSerializer(req).data,
            },
            status=status.HTTP_200_OK,
        )


class StudentRegistrationRequestViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Institution Admin viewset to review, verify, approve, or reject student registration requests.
    Strictly tenant-scoped.
    """
    serializer_class = StudentRegistrationRequestSerializer
    permission_classes = [IsInstitutionAdmin]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["first_name", "last_name", "email", "admission_number", "grade_or_program"]
    ordering_fields = ["created_at", "last_requested_at", "admission_number"]
    ordering = ["-last_requested_at"]

    def get_queryset(self):
        tenant = get_or_resolve_tenant(self.request)
        if not tenant:
            return StudentRegistrationRequest.objects.none()

        qs = StudentRegistrationRequest.objects.filter(tenant=tenant)
        req_status = self.request.query_params.get("status")
        if req_status:
            qs = qs.filter(status=req_status)
        return qs

    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        """
        Approves a student registration request:
        1. Activates user account
        2. Grants active tenant membership with 'student' role
        3. Creates Student profile in this tenant
        4. Updates request status to 'approved'
        """
        tenant = get_or_resolve_tenant(request)
        reg_req = self.get_object()

        if reg_req.status == StudentRegistrationRequest.STATUS_APPROVED:
            return Response(
                {"success": True, "message": "This request is already approved."},
                status=status.HTTP_200_OK,
            )

        with transaction.atomic():
            # 1. Update Request
            reg_req.status = StudentRegistrationRequest.STATUS_APPROVED
            reg_req.reviewed_at = timezone.now()
            reg_req.reviewed_by = request.user
            reg_req.rejection_reason = ""
            reg_req.save()

            # 2. Activate User
            user = reg_req.user
            if not user:
                user, _ = User.objects.get_or_create(
                    email=reg_req.email,
                    defaults={
                        "first_name": reg_req.first_name,
                        "last_name": reg_req.last_name,
                        "phone_number": reg_req.phone_number,
                    },
                )
            user.is_active = True
            user.first_name = reg_req.first_name
            user.last_name = reg_req.last_name
            if reg_req.phone_number:
                user.phone_number = reg_req.phone_number
            user.save()

            # 3. Create / Activate Tenant Membership
            membership, _ = Membership.objects.get_or_create(
                user=user,
                tenant=tenant,
                defaults={
                    "status": Membership.STATUS_ACTIVE,
                    "is_default": True,
                },
            )
            membership.status = Membership.STATUS_ACTIVE
            membership.save()

            # 4. Attach Student Role
            student_role = Role.objects.filter(tenant=tenant, code=Role.CODE_STUDENT).first()
            if not student_role:
                student_role = Role.objects.filter(tenant__isnull=True, code=Role.CODE_STUDENT).first()
            if not student_role:
                student_role = Role.objects.create(
                    tenant=tenant,
                    code=Role.CODE_STUDENT,
                    name="Student",
                    description="Standard student learner role",
                )

            MembershipRole.objects.get_or_create(membership=membership, role=student_role)

            # 5. Create Student profile (if not exists)
            student, _ = Student.objects.get_or_create(
                tenant=tenant,
                admission_number=reg_req.admission_number,
                defaults={
                    "user": user,
                    "first_name": reg_req.first_name,
                    "last_name": reg_req.last_name,
                    "gender": reg_req.gender or Student.GENDER_FEMALE,
                    "date_of_birth": reg_req.date_of_birth,
                    "status": Student.STATUS_ADMITTED,
                },
            )
            if not student.user:
                student.user = user
                student.save(update_fields=["user"])

            # 6. Audit Trail
            log_audit_event(
                action="STUDENT_REQUEST_APPROVED",
                resource_type="StudentRegistrationRequest",
                resource_id=str(reg_req.id),
                tenant=tenant,
                actor=request.user,
                description=f"Approved student registration for {reg_req.applicant_name} ({reg_req.admission_number}).",
                request=request,
            )

        return Response(
            {
                "success": True,
                "message": f"Student '{reg_req.applicant_name}' has been verified and enrolled successfully.",
                "data": StudentRegistrationRequestSerializer(reg_req).data,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        """
        Rejects a student registration request:
        - If permanent=True: flags as false/fraudulent request, blacklisting applicant from re-requesting.
        - If permanent=False: allows re-request after backend configured cooldown period.
        """
        tenant = get_or_resolve_tenant(request)
        reg_req = self.get_object()

        permanent = bool(request.data.get("permanent", False))
        reason = str(request.data.get("reason", "")).strip()

        if permanent:
            reg_req.status = StudentRegistrationRequest.STATUS_PERMANENTLY_REJECTED
            desc = f"Permanently rejected (blacklisted) student request for {reg_req.applicant_name}. Reason: {reason or 'False application'}"
        else:
            reg_req.status = StudentRegistrationRequest.STATUS_REJECTED
            desc = f"Rejected student request for {reg_req.applicant_name}. Reason: {reason or 'Revision required'}"

        reg_req.rejection_reason = reason
        reg_req.reviewed_at = timezone.now()
        reg_req.reviewed_by = request.user
        reg_req.save()

        # Keep user inactive
        if reg_req.user:
            reg_req.user.is_active = False
            reg_req.user.save(update_fields=["is_active"])

        log_audit_event(
            action="STUDENT_REQUEST_PERMANENTLY_REJECTED" if permanent else "STUDENT_REQUEST_REJECTED",
            resource_type="StudentRegistrationRequest",
            resource_id=str(reg_req.id),
            tenant=tenant,
            actor=request.user,
            description=desc,
            request=request,
        )

        return Response(
            {
                "success": True,
                "message": "Student request rejected permanently." if permanent else "Student request rejected. The student may re-request after the cooldown period.",
                "data": StudentRegistrationRequestSerializer(reg_req).data,
            },
            status=status.HTTP_200_OK,
        )
