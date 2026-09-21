from rest_framework import serializers
from apps.students.models import Student, StudentRegistrationRequest
from apps.students.services import admit_student_service
from apps.guardians.models import StudentGuardian
from apps.tenants.models import Tenant
from apps.accounts.permissions import get_or_resolve_tenant


class StudentGuardianListSerializer(serializers.ModelSerializer):
    guardian_name = serializers.CharField(source="guardian.first_name", read_only=True)
    phone_number = serializers.CharField(source="guardian.phone_number", read_only=True)

    class Meta:
        model = StudentGuardian
        fields = ["id", "guardian_name", "relationship", "phone_number", "is_primary"]


class StudentSerializer(serializers.ModelSerializer):
    guardian_links = StudentGuardianListSerializer(many=True, read_only=True)
    email = serializers.CharField(source="user.email", read_only=True, default="")
    user_id = serializers.UUIDField(source="user.id", read_only=True, default=None)
    avatar_url = serializers.CharField(source="user.avatar_url", read_only=True, default="")
    class_cohort_name = serializers.SerializerMethodField()
    section_name = serializers.SerializerMethodField()

    class Meta:
        model = Student
        fields = [
            "id",
            "admission_number",
            "first_name",
            "last_name",
            "full_name",
            "date_of_birth",
            "gender",
            "blood_group",
            "status",
            "admission_date",
            "avatar_url",
            "email",
            "user_id",
            "class_cohort_name",
            "section_name",
            "guardian_links",
            "created_at",
        ]
        read_only_fields = ["id", "admission_number", "created_at"]

    def get_class_cohort_name(self, obj):
        enrollment = obj.enrollments.filter(status="enrolled").select_related("class_cohort").first()
        return enrollment.class_cohort.name if enrollment and enrollment.class_cohort else ""

    def get_section_name(self, obj):
        enrollment = obj.enrollments.filter(status="enrolled").select_related("section").first()
        return enrollment.section.name if enrollment and enrollment.section else ""


class StudentAdmissionSerializer(serializers.Serializer):
    """
    Serializer for the multi-step student admission workflow.
    Accepts student details, optional guardian, and optional class enrollment data.
    """
    # Student Details
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    email = serializers.EmailField(required=False, allow_blank=True)
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    gender = serializers.ChoiceField(choices=Student.GENDER_CHOICES, default=Student.GENDER_MALE)
    blood_group = serializers.CharField(max_length=10, required=False, allow_blank=True, default="")
    admission_date = serializers.DateField(required=False, allow_null=True)
    admission_number = serializers.CharField(max_length=50, required=False, allow_blank=True)
    tenant_id = serializers.UUIDField(required=False, allow_null=True)

    # Optional Guardian Details
    guardian = serializers.DictField(required=False)

    # Optional Enrollment Details
    academic_year_id = serializers.UUIDField(required=False)
    class_cohort_id = serializers.UUIDField(required=False)
    section_id = serializers.UUIDField(required=False)
    class_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    section_name = serializers.CharField(max_length=50, required=False, allow_blank=True)
    roll_number = serializers.CharField(max_length=50, required=False, allow_blank=True)

    def create(self, validated_data):
        request = self.context.get("request")
        tenant = get_or_resolve_tenant(request) if request else None

        explicit_tenant_id = validated_data.pop("tenant_id", None)
        if not tenant and explicit_tenant_id:
            tenant = Tenant.objects.filter(id=explicit_tenant_id, is_deleted=False).first()

        if not tenant:
            raise serializers.ValidationError({
                "tenant": "A valid educational institution / tenant context is required to admit students. Please select an organization."
            })

        actor = request.user if request else None

        guardian_data = validated_data.pop("guardian", None)
        academic_year_id = validated_data.pop("academic_year_id", None)
        class_cohort_id = validated_data.pop("class_cohort_id", None)
        section_id = validated_data.pop("section_id", None)
        class_name = validated_data.pop("class_name", "")
        section_name = validated_data.pop("section_name", "")
        roll_number = validated_data.pop("roll_number", "")

        enrollment_data = {
            "academic_year_id": academic_year_id,
            "class_cohort_id": class_cohort_id,
            "section_id": section_id,
            "class_name": class_name,
            "section_name": section_name,
            "roll_number": roll_number,
        }

        student = admit_student_service(
            tenant=tenant,
            student_data=validated_data,
            guardian_data=guardian_data,
            enrollment_data=enrollment_data,
            actor=actor,
            request=request,
        )
        return student


class StudentRegistrationRequestSerializer(serializers.ModelSerializer):
    tenant_name = serializers.CharField(source="tenant.name", read_only=True)
    tenant_slug = serializers.CharField(source="tenant.slug", read_only=True)
    applicant_name = serializers.CharField(read_only=True)
    reviewed_by_email = serializers.CharField(source="reviewed_by.email", read_only=True, default="")
    can_re_request = serializers.SerializerMethodField()
    re_request_cooldown_remaining_hours = serializers.SerializerMethodField()
    eligible_re_request_at = serializers.SerializerMethodField()

    class Meta:
        model = StudentRegistrationRequest
        fields = [
            "id",
            "tenant",
            "tenant_name",
            "tenant_slug",
            "user",
            "email",
            "first_name",
            "last_name",
            "applicant_name",
            "phone_number",
            "admission_number",
            "grade_or_program",
            "gender",
            "date_of_birth",
            "notes",
            "status",
            "last_requested_at",
            "re_request_count",
            "reviewed_at",
            "reviewed_by",
            "reviewed_by_email",
            "rejection_reason",
            "can_re_request",
            "re_request_cooldown_remaining_hours",
            "eligible_re_request_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "tenant",
            "user",
            "status",
            "last_requested_at",
            "re_request_count",
            "reviewed_at",
            "reviewed_by",
            "rejection_reason",
            "created_at",
            "updated_at",
        ]

    def get_can_re_request(self, obj):
        can_re, _, _ = obj.can_re_request()
        return can_re

    def get_re_request_cooldown_remaining_hours(self, obj):
        can_re, remaining, _ = obj.can_re_request()
        if not can_re and remaining:
            return round(remaining.total_seconds() / 3600, 1)
        return 0

    def get_eligible_re_request_at(self, obj):
        from django.conf import settings
        from datetime import timedelta
        gap_hours = getattr(settings, "STUDENT_REGISTRATION_REREQUEST_GAP_HOURS", 24)
        if obj.last_requested_at:
            return (obj.last_requested_at + timedelta(hours=gap_hours)).isoformat()
        return None


class StudentSelfRegisterSerializer(serializers.Serializer):
    tenant_id = serializers.CharField(required=True)
    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True, required=True, min_length=6)
    first_name = serializers.CharField(max_length=150, required=True)
    last_name = serializers.CharField(max_length=150, required=True)
    phone_number = serializers.CharField(max_length=50, required=False, allow_blank=True, default="")
    admission_number = serializers.CharField(max_length=50, required=True)
    grade_or_program = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    gender = serializers.ChoiceField(choices=Student.GENDER_CHOICES, default=Student.GENDER_FEMALE)
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True, default="")

