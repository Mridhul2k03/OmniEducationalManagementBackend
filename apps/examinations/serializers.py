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
    exam_id = serializers.UUIDField(source="exam_subject.exam_id", read_only=True)
    max_marks = serializers.DecimalField(source="exam_subject.max_marks", max_digits=6, decimal_places=2, read_only=True)
    grade = serializers.SerializerMethodField()
    grade_point = serializers.SerializerMethodField()

    class Meta:
        model = Mark
        fields = [
            "id",
            "exam_subject",
            "exam_id",
            "subject_name",
            "student",
            "student_name",
            "admission_number",
            "marks_obtained",
            "max_marks",
            "grade",
            "grade_point",
            "is_absent",
            "remarks",
            "status",
            "entered_by",
            "created_at",
        ]
        read_only_fields = ["id", "entered_by", "created_at", "exam_id", "max_marks", "grade", "grade_point"]

    def get_grade(self, obj):
        if obj.is_absent or obj.marks_obtained is None:
            return "F"
        max_m = obj.exam_subject.max_marks or 100
        if max_m <= 0:
            return "F"
        pct = float((obj.marks_obtained / max_m) * 100)
        if pct >= 90:
            return "A+"
        if pct >= 80:
            return "A"
        if pct >= 70:
            return "B+"
        if pct >= 60:
            return "B"
        if pct >= 50:
            return "C"
        if pct >= 40:
            return "D"
        return "F"

    def get_grade_point(self, obj):
        if obj.is_absent or obj.marks_obtained is None:
            return 0.0
        max_m = obj.exam_subject.max_marks or 100
        if max_m <= 0:
            return 0.0
        pct = float((obj.marks_obtained / max_m) * 100)
        if pct >= 90:
            return 4.0
        if pct >= 80:
            return 3.7
        if pct >= 70:
            return 3.3
        if pct >= 60:
            return 3.0
        if pct >= 50:
            return 2.0
        if pct >= 40:
            return 1.0
        return 0.0

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

