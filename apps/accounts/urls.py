from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.accounts.views import (
    RegisterInstitutionView,
    CustomLoginView,
    CustomTokenRefreshView,
    LogoutView,
    MeView,
    AuthCheckView,
    SwitchTenantView,
    RoleViewSet,
    MembershipViewSet,
    InstitutionUserViewSet,
    PermissionListView,
)
from apps.students.registration_views import (
    StudentRegisterView,
    StudentLoginView,
    StudentReRequestView,
    StudentCheckStatusView,
)

router = DefaultRouter()
router.register(r"roles", RoleViewSet, basename="role")
router.register(r"memberships", MembershipViewSet, basename="membership")
router.register(r"institution-users", InstitutionUserViewSet, basename="institution-user")

urlpatterns = [
    # Auth endpoints
    path("auth/register-institution/", RegisterInstitutionView.as_view(), name="register-institution"),
    path("auth/login/", CustomLoginView.as_view(), name="login"),
    path("auth/refresh/", CustomTokenRefreshView.as_view(), name="token-refresh"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("auth/check/", AuthCheckView.as_view(), name="auth-check"),
    path("auth/me/", MeView.as_view(), name="auth-me"),
    path("auth/switch-tenant/", SwitchTenantView.as_view(), name="switch-tenant"),

    # Student Auth & Verification Endpoints
    path("auth/student-register/", StudentRegisterView.as_view(), name="student-register"),
    path("auth/student-login/", StudentLoginView.as_view(), name="student-login"),
    path("auth/student-rerequest/", StudentReRequestView.as_view(), name="student-rerequest"),
    path("auth/student-status/", StudentCheckStatusView.as_view(), name="student-status"),

    path("permissions/", PermissionListView.as_view(), name="permission-list"),
    path("", include(router.urls)),
]
