from rest_framework import serializers
from apps.examinations.models import GradeScale, Exam, ExamSubject, Mark


class GradeScaleSerializer(serializers.ModelSerializer):
    class Meta:
        model = GradeScale
        fields = ["id", "name", "description", "rules"]
        read_only_fields = ["id"]


class ExamSubjectSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source="subject.name", read_only=True)

    class Meta:
        model = ExamSubject
        fields = [
            "id",
            "exam",
            "subject",
            "subject_name",
            "exam_date",
            "start_time",
            "end_time",
            "max_marks",
            "passing_marks",
        ]
        read_only_fields = ["id"]


class ExamSerializer(serializers.ModelSerializer):
    class_cohort_name = serializers.CharField(source="class_cohort.name", read_only=True)
    exam_subjects = ExamSubjectSerializer(many=True, read_only=True)

    class Meta:
        model = Exam
        fields = [
            "id",
            "academic_year",
            "term",
            "class_cohort",
            "class_cohort_name",
            "name",
            "exam_type",
            "start_date",
            "end_date",
            "status",
            "is_published",
            "published_at",
            "exam_subjects",
            "created_at",
        ]
        read_only_fields = ["id", "is_published", "published_at", "created_at"]


class MarkSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.full_name", read_only=True)
    admission_number = serializers.CharField(source="student.admission_number", read_only=True)
    subject_name = serializers.CharField(source="exam_subject.subject.name", read_only=True)

    class Meta:
        model = Mark
        fields = [
            "id",
            "exam_subject",
            "subject_name",
            "student",
            "student_name",
            "admission_number",
            "marks_obtained",
            "is_absent",
            "remarks",
            "status",
            "entered_by",
            "created_at",
        ]
        read_only_fields = ["id", "entered_by", "created_at"]

    def validate(self, attrs):
        exam_subject = attrs.get("exam_subject") or (self.instance.exam_subject if self.instance else None)
        if exam_subject and exam_subject.exam.is_published:
            raise serializers.ValidationError("Cannot modify marks for an already published examination.")

        is_absent = attrs.get("is_absent", self.instance.is_absent if self.instance else False)
        marks = attrs.get("marks_obtained", self.instance.marks_obtained if self.instance else None)

        if not is_absent:
            if marks is None:
                raise serializers.ValidationError({"marks_obtained": "Marks obtained must be provided unless marked absent."})
            if marks < 0:
                raise serializers.ValidationError({"marks_obtained": "Marks cannot be negative."})
            if exam_subject and marks > exam_subject.max_marks:
                raise serializers.ValidationError({"marks_obtained": f"Marks ({marks}) cannot exceed max marks ({exam_subject.max_marks})."})

        return attrs
