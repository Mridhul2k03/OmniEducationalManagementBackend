from rest_framework import serializers
from apps.academics.models import AcademicYear, Term, Department, Course, Subject, ClassCohort, Section


class AcademicYearSerializer(serializers.ModelSerializer):
    class Meta:
        model = AcademicYear
        fields = ["id", "name", "start_date", "end_date", "is_current", "created_at"]
        read_only_fields = ["id", "created_at"]


class TermSerializer(serializers.ModelSerializer):
    academic_year_name = serializers.CharField(source="academic_year.name", read_only=True)

    class Meta:
        model = Term
        fields = ["id", "academic_year", "academic_year_name", "name", "start_date", "end_date", "is_current"]
        read_only_fields = ["id"]


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ["id", "name", "code", "created_at"]
        read_only_fields = ["id", "created_at"]


class CourseSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source="department.name", read_only=True)

    class Meta:
        model = Course
        fields = ["id", "department", "department_name", "name", "code", "credits"]
        read_only_fields = ["id"]


class SubjectSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source="department.name", read_only=True)

    class Meta:
        model = Subject
        fields = ["id", "department", "department_name", "name", "code", "subject_type"]
        read_only_fields = ["id"]


class SectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Section
        fields = ["id", "class_cohort", "name", "room_number", "capacity"]
        read_only_fields = ["id"]


class ClassCohortSerializer(serializers.ModelSerializer):
    academic_year_name = serializers.CharField(source="academic_year.name", read_only=True)
    sections = SectionSerializer(many=True, read_only=True)

    class Meta:
        model = ClassCohort
        fields = ["id", "academic_year", "academic_year_name", "course", "name", "sections"]
        read_only_fields = ["id"]
