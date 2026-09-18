from rest_framework import serializers
from apps.tenants.models import Tenant


class TenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = [
            "id",
            "name",
            "legal_name",
            "slug",
            "institution_type",
            "status",
            "timezone",
            "locale",
            "currency",
            "logo_url",
            "branding_metadata",
            "address",
            "contact_email",
            "contact_phone",
            "subscription_reference",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class TenantDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = [
            "id",
            "name",
            "legal_name",
            "slug",
            "institution_type",
            "status",
            "timezone",
            "locale",
            "currency",
            "logo_url",
            "branding_metadata",
            "address",
            "contact_email",
            "contact_phone",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "slug", "created_at", "updated_at"]
