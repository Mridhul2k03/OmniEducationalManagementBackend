from rest_framework import serializers
from apps.students.models import Student
from apps.students.services import admit_student_service
from apps.guardians.models import StudentGuardian


class StudentGuardianListSerializer(serializers.ModelSerializer):
    guardian_name = serializers.CharField(source="guardian.first_name", read_only=True)
    phone_number = serializers.CharField(source="guardian.phone_number", read_only=True)

    class Meta:
        model = StudentGuardian
        fields = ["id", "guardian_name", "relationship", "phone_number", "is_primary"]


class StudentSerializer(serializers.ModelSerializer):
    guardian_links = StudentGuardianListSerializer(many=True, read_only=True)

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
            "admission_date",
            "status",
            "emergency_contact",
            "guardian_links",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class StudentAdmissionSerializer(serializers.Serializer):
    """
    Input serializer for the multi-step admission workflow.
    """
    # Student Details
    admission_number = serializers.CharField(max_length=50, required=False, allow_blank=True)
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    date_of_birth = serializers.DateField()
    gender = serializers.ChoiceField(choices=Student.GENDER_CHOICES)
    blood_group = serializers.CharField(max_length=10, required=False, allow_blank=True)
    admission_date = serializers.DateField()
    medical_notes = serializers.CharField(required=False, allow_blank=True)

    # Optional Guardian Details
    guardian = serializers.DictField(required=False)

    # Optional Enrollment Details
    academic_year_id = serializers.UUIDField(required=False)
    class_cohort_id = serializers.UUIDField(required=False)
    section_id = serializers.UUIDField(required=False)
    roll_number = serializers.CharField(max_length=50, required=False, allow_blank=True)

    def create(self, validated_data):
        request = self.context.get("request")
        tenant = request.tenant
        actor = request.user

        guardian_data = validated_data.pop("guardian", None)
        academic_year_id = validated_data.pop("academic_year_id", None)
        class_cohort_id = validated_data.pop("class_cohort_id", None)
        section_id = validated_data.pop("section_id", None)
        roll_number = validated_data.pop("roll_number", "")

        enrollment_data = None
        if academic_year_id and class_cohort_id and section_id:
            enrollment_data = {
                "academic_year_id": academic_year_id,
                "class_cohort_id": class_cohort_id,
                "section_id": section_id,
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
