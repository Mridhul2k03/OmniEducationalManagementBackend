from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from apps.communications.models import Announcement, Notification
from apps.communications.serializers import AnnouncementSerializer, NotificationSerializer
from apps.accounts.permissions import IsInstitutionAdmin, IsTenantMember


class AnnouncementViewSet(viewsets.ModelViewSet):
    queryset = Announcement.objects.none()
    serializer_class = AnnouncementSerializer

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsInstitutionAdmin()]
        return [IsTenantMember()]

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        if getattr(self, "swagger_fake_view", False) or not tenant:
            return Announcement.objects.none()
        return Announcement.objects.filter(tenant=tenant, is_published=True)

    def perform_create(self, serializer):
        serializer.save(
            tenant=self.request.tenant,
            created_by=self.request.user,
        )


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Notification.objects.none()
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False) or not self.request.user.is_authenticated:
            return Notification.objects.none()
        # User can only view their own notifications
        return Notification.objects.filter(recipient=self.request.user)

    @action(detail=True, methods=["post"], url_path="mark-read")
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        notification.is_read = True
        notification.save(update_fields=["is_read"])
        return Response({"success": True, "message": "Notification marked as read."})
