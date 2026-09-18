from rest_framework import serializers
from apps.communications.models import Announcement, Notification


class AnnouncementSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source="created_by.full_name", read_only=True)

    class Meta:
        model = Announcement
        fields = [
            "id",
            "title",
            "content",
            "target_audience",
            "is_published",
            "published_at",
            "author_name",
        ]
        read_only_fields = ["id", "published_at", "author_name"]


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            "id",
            "title",
            "message",
            "channel",
            "is_read",
            "sent_at",
        ]
        read_only_fields = ["id", "title", "message", "channel", "sent_at"]
