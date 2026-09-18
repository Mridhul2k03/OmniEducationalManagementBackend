"""
Finance, Fee Structures, Invoicing, Payments, and Receipts models. Strictly tenant-scoped.
"""
from decimal import Decimal
from django.db import models
from django.core.exceptions import ValidationError
from apps.common.models import TenantScopedModel


class FeeCategory(TenantScopedModel):
    name = models.CharField(max_length=100)  # e.g. "Tuition Fee", "Lab Fee", "Transport Fee"
    description = models.TextField(blank=True, default="")

    class Meta:
        db_table = "fee_categories"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "name"],
                name="unique_tenant_fee_category",
            )
        ]

    def __str__(self):
        return self.name


class FeeStructure(TenantScopedModel):
    academic_year = models.ForeignKey(
        "academics.AcademicYear",
        on_delete=models.CASCADE,
        related_name="fee_structures",
    )
    class_cohort = models.ForeignKey(
        "academics.ClassCohort",
        on_delete=models.CASCADE,
        related_name="fee_structures",
    )
    category = models.ForeignKey(
        FeeCategory,
        on_delete=models.CASCADE,
        related_name="structures",
    )
    name = models.CharField(max_length=150)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    due_date = models.DateField()

    class Meta:
        db_table = "fee_structures"
        ordering = ["due_date"]

    def __str__(self):
        return f"{self.name} - {self.class_cohort.name}: {self.amount}"


class Invoice(TenantScopedModel):
    STATUS_DRAFT = "draft"
    STATUS_ISSUED = "issued"
    STATUS_PARTIALLY_PAID = "partially_paid"
    STATUS_PAID = "paid"
    STATUS_OVERDUE = "overdue"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = (
        (STATUS_DRAFT, "Draft"),
        (STATUS_ISSUED, "Issued"),
        (STATUS_PARTIALLY_PAID, "Partially Paid"),
        (STATUS_PAID, "Paid"),
        (STATUS_OVERDUE, "Overdue"),
        (STATUS_CANCELLED, "Cancelled"),
    )

    invoice_number = models.CharField(max_length=50, db_index=True)
    student = models.ForeignKey(
        "students.Student",
        on_delete=models.CASCADE,
        related_name="invoices",
        db_index=True,
    )
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    balance_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ISSUED, db_index=True)
    due_date = models.DateField()

    class Meta:
        db_table = "invoices"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "invoice_number"],
                name="unique_tenant_invoice_number",
            )
        ]
        indexes = [
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["student", "status"]),
        ]

    def __str__(self):
        return f"Invoice {self.invoice_number} ({self.student.full_name}) - Balance: {self.balance_amount}"


class InvoiceLine(TenantScopedModel):
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    fee_structure = models.ForeignKey(
        FeeStructure,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        db_table = "invoice_lines"


class Payment(TenantScopedModel):
    METHOD_CASH = "cash"
    METHOD_BANK = "bank_transfer"
    METHOD_CARD = "card"
    METHOD_ONLINE = "online"

    PAYMENT_METHOD_CHOICES = (
        (METHOD_CASH, "Cash"),
        (METHOD_BANK, "Bank Transfer"),
        (METHOD_CARD, "Debit/Credit Card"),
        (METHOD_ONLINE, "Online Gateway"),
    )

    STATUS_SUCCESS = "success"
    STATUS_PENDING = "pending"
    STATUS_FAILED = "failed"

    STATUS_CHOICES = (
        (STATUS_SUCCESS, "Success"),
        (STATUS_PENDING, "Pending"),
        (STATUS_FAILED, "Failed"),
    )

    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name="payments",
        db_index=True,
    )
    receipt_number = models.CharField(max_length=50, db_index=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default=METHOD_CASH)
    transaction_reference = models.CharField(max_length=100, blank=True, default="")
    # Idempotency key to prevent duplicate online/offline charges
    idempotency_key = models.CharField(max_length=100, null=True, blank=True, unique=True, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_SUCCESS, db_index=True)
    payment_date = models.DateTimeField(auto_now_add=True)
    recorded_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recorded_payments",
    )

    class Meta:
        db_table = "payments"
        ordering = ["-payment_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "receipt_number"],
                name="unique_tenant_receipt_number",
            )
        ]

    def __str__(self):
        return f"Receipt {self.receipt_number} - Amount: {self.amount}"
