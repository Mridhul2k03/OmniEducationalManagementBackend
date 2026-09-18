from rest_framework import serializers
from apps.staff.models import Staff
from apps.accounts.serializers import UserSerializer


class StaffSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="user.full_name", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)

    class Meta:
        model = Staff
        fields = [
            "id",
            "employee_id",
            "user",
            "full_name",
            "email",
            "department",
            "department_name",
            "designation",
            "qualification",
            "joined_date",
            "employment_type",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
