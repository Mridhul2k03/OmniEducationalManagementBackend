from rest_framework import serializers
from apps.attendance.models import AttendanceRecord, AttendanceCorrectionRequest


class AttendanceRecordSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.full_name", read_only=True)
    admission_number = serializers.CharField(source="student.admission_number", read_only=True)

    class Meta:
        model = AttendanceRecord
        fields = [
            "id",
            "student",
            "student_name",
            "admission_number",
            "section",
            "subject",
            "date",
            "status",
            "remarks",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class BulkAttendanceEntryItemSerializer(serializers.Serializer):
    student_id = serializers.UUIDField()
    status = serializers.ChoiceField(choices=AttendanceRecord.STATUS_CHOICES)
    remarks = serializers.CharField(required=False, allow_blank=True, default="")


class BulkAttendanceSubmissionSerializer(serializers.Serializer):
    section_id = serializers.UUIDField()
    subject_id = serializers.UUIDField(required=False, allow_null=True)
    date = serializers.DateField()
    entries = BulkAttendanceEntryItemSerializer(many=True)


class AttendanceCorrectionRequestSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="attendance_record.student.full_name", read_only=True)

    class Meta:
        model = AttendanceCorrectionRequest
        fields = [
            "id",
            "attendance_record",
            "student_name",
            "requested_status",
            "reason",
            "status",
            "requested_by",
            "reviewed_by",
            "reviewed_at",
            "created_at",
        ]
        read_only_fields = ["id", "status", "requested_by", "reviewed_by", "reviewed_at", "created_at"]
