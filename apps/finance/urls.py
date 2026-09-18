from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.finance.views import (
    FeeCategoryViewSet,
    FeeStructureViewSet,
    InvoiceViewSet,
    PaymentViewSet,
)

router = DefaultRouter()
router.register(r"categories", FeeCategoryViewSet, basename="fee-category")
router.register(r"structures", FeeStructureViewSet, basename="fee-structure")
router.register(r"invoices", InvoiceViewSet, basename="invoice")
router.register(r"payments", PaymentViewSet, basename="payment")

urlpatterns = [
    path("", include(router.urls)),
]
