from decimal import Decimal
from rest_framework import serializers
from apps.finance.models import FeeCategory, FeeStructure, Invoice, InvoiceLine, Payment
from apps.finance.services import generate_invoice_service, record_payment_service


class FeeCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = FeeCategory
        fields = ["id", "name", "description"]
        read_only_fields = ["id"]


class FeeStructureSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    class_cohort_name = serializers.CharField(source="class_cohort.name", read_only=True)

    class Meta:
        model = FeeStructure
        fields = [
            "id",
            "academic_year",
            "class_cohort",
            "class_cohort_name",
            "category",
            "category_name",
            "name",
            "amount",
            "due_date",
        ]
        read_only_fields = ["id"]


class InvoiceLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceLine
        fields = ["id", "description", "amount"]
        read_only_fields = ["id"]


class PaymentSerializer(serializers.ModelSerializer):
    invoice_number = serializers.CharField(source="invoice.invoice_number", read_only=True)

    class Meta:
        model = Payment
        fields = [
            "id",
            "invoice",
            "invoice_number",
            "receipt_number",
            "amount",
            "payment_method",
            "transaction_reference",
            "idempotency_key",
            "status",
            "payment_date",
        ]
        read_only_fields = ["id", "receipt_number", "status", "payment_date"]


class InvoiceSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.full_name", read_only=True)
    admission_number = serializers.CharField(source="student.admission_number", read_only=True)
    lines = InvoiceLineSerializer(many=True, read_only=True)
    payments = PaymentSerializer(many=True, read_only=True)

    class Meta:
        model = Invoice
        fields = [
            "id",
            "invoice_number",
            "student",
            "student_name",
            "admission_number",
            "total_amount",
            "discount_amount",
            "paid_amount",
            "balance_amount",
            "status",
            "due_date",
            "lines",
            "payments",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "invoice_number",
            "total_amount",
            "paid_amount",
            "balance_amount",
            "status",
            "created_at",
        ]


class GenerateInvoiceInputSerializer(serializers.Serializer):
    student_id = serializers.UUIDField()
    fee_structure_ids = serializers.ListField(child=serializers.UUIDField())
    due_date = serializers.DateField()
    discount_amount = serializers.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"), required=False)


class RecordPaymentInputSerializer(serializers.Serializer):
    invoice_id = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    payment_method = serializers.ChoiceField(choices=Payment.PAYMENT_METHOD_CHOICES, default=Payment.METHOD_CASH)
    transaction_reference = serializers.CharField(required=False, allow_blank=True, default="")
    idempotency_key = serializers.CharField(required=False, allow_blank=True, allow_null=True)
