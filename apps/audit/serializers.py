from rest_framework import serializers
from apps.audit.models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    actor_email = serializers.EmailField(source="actor.email", read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "tenant",
            "actor",
            "actor_email",
            "action",
            "resource_type",
            "resource_id",
            "description",
            "changes",
            "ip_address",
            "user_agent",
            "request_id",
            "created_at",
        ]
        read_only_fields = fields
