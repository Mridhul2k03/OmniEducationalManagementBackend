from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.accounts.views import (
    RegisterInstitutionView,
    CustomLoginView,
    CustomTokenRefreshView,
    LogoutView,
    MeView,
    SwitchTenantView,
    RoleViewSet,
    MembershipViewSet,
    PermissionListView,
)

router = DefaultRouter()
router.register(r"roles", RoleViewSet, basename="role")
router.register(r"memberships", MembershipViewSet, basename="membership")

urlpatterns = [
    # Auth endpoints
    path("auth/register-institution/", RegisterInstitutionView.as_view(), name="register-institution"),
    path("auth/login/", CustomLoginView.as_view(), name="login"),
    path("auth/refresh/", CustomTokenRefreshView.as_view(), name="token-refresh"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("auth/me/", MeView.as_view(), name="auth-me"),
    path("auth/switch-tenant/", SwitchTenantView.as_view(), name="switch-tenant"),
    path("permissions/", PermissionListView.as_view(), name="permission-list"),
    path("", include(router.urls)),
]
