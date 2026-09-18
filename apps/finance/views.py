from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from apps.finance.models import FeeCategory, FeeStructure, Invoice, Payment
from apps.finance.serializers import (
    FeeCategorySerializer,
    FeeStructureSerializer,
    InvoiceSerializer,
    PaymentSerializer,
    GenerateInvoiceInputSerializer,
    RecordPaymentInputSerializer,
)
from apps.finance.services import generate_invoice_service, record_payment_service
from apps.accounts.permissions import HasTenantPermission, IsTenantMember


class FeeCategoryViewSet(viewsets.ModelViewSet):
    serializer_class = FeeCategorySerializer
    permission_classes = [HasTenantPermission("fees.view")]

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        if not tenant:
            return FeeCategory.objects.none()
        return FeeCategory.objects.filter(tenant=tenant)

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.tenant, created_by=self.request.user)


class FeeStructureViewSet(viewsets.ModelViewSet):
    serializer_class = FeeStructureSerializer
    permission_classes = [HasTenantPermission("fees.view")]

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        if not tenant:
            return FeeStructure.objects.none()
        return FeeStructure.objects.filter(tenant=tenant).select_related("category", "class_cohort")

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.tenant, created_by=self.request.user)


class InvoiceViewSet(viewsets.ModelViewSet):
    queryset = Invoice.objects.none()
    serializer_class = InvoiceSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["student", "status"]

    def get_permissions(self):
        if self.action in ["create", "generate_invoice"]:
            return [HasTenantPermission("fees.create_invoice")()]
        return [HasTenantPermission("fees.view")()]

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        if getattr(self, "swagger_fake_view", False) or not tenant:
            return Invoice.objects.none()

        user = self.request.user
        qs = Invoice.objects.filter(tenant=tenant).select_related("student").prefetch_related("lines", "payments")

        # Students can view only their own invoices
        if hasattr(user, "student_profile"):
            return qs.filter(student=user.student_profile)

        return qs

    @action(detail=False, methods=["post"], url_path="generate")
    def generate_invoice(self, request):
        """
        Generates an invoice from fee structures.
        """
        serializer = GenerateInvoiceInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        invoice = generate_invoice_service(
            tenant=request.tenant,
            student_id=data["student_id"],
            fee_structure_ids=data["fee_structure_ids"],
            due_date=data["due_date"],
            discount_amount=data.get("discount_amount", 0),
            actor=request.user,
            request=request,
        )

        return Response(
            {
                "success": True,
                "message": f"Invoice {invoice.invoice_number} generated successfully.",
                "data": InvoiceSerializer(invoice).data,
            },
            status=status.HTTP_201_CREATED,
        )


class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.none()
    serializer_class = PaymentSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["invoice", "status", "payment_method"]

    def get_permissions(self):
        if self.action in ["create", "record_payment"]:
            return [HasTenantPermission("fees.record_payment")()]
        return [HasTenantPermission("fees.view")()]

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        if getattr(self, "swagger_fake_view", False) or not tenant:
            return Payment.objects.none()
        return Payment.objects.filter(tenant=tenant).select_related("invoice__student")

    @action(detail=False, methods=["post"], url_path="record")
    def record_payment(self, request):
        """
        Records a payment transaction against an outstanding invoice with idempotency.
        """
        serializer = RecordPaymentInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        payment = record_payment_service(
            tenant=request.tenant,
            invoice_id=data["invoice_id"],
            amount=data["amount"],
            payment_method=data.get("payment_method", Payment.METHOD_CASH),
            transaction_reference=data.get("transaction_reference", ""),
            idempotency_key=data.get("idempotency_key"),
            actor=request.user,
            request=request,
        )

        return Response(
            {
                "success": True,
                "message": f"Payment recorded successfully. Receipt: {payment.receipt_number}.",
                "data": PaymentSerializer(payment).data,
            },
            status=status.HTTP_201_CREATED,
        )
