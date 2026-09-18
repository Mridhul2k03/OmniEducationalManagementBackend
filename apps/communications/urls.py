from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.communications.views import AnnouncementViewSet, NotificationViewSet

router = DefaultRouter()
router.register(r"announcements", AnnouncementViewSet, basename="announcement")
router.register(r"notifications", NotificationViewSet, basename="notification")

urlpatterns = [
    path("", include(router.urls)),
]
