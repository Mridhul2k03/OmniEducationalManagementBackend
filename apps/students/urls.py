from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.students.views import StudentViewSet

router = DefaultRouter()
router.register(r"", StudentViewSet, basename="student")

urlpatterns = [
    path("", include(router.urls)),
]
