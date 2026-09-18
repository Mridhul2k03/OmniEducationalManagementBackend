"""
Finance Domain Services: Invoice Generation, Idempotent Payment Processing, and Receipts.
"""
from decimal import Decimal
from django.db import transaction
from rest_framework.exceptions import ValidationError
from apps.finance.models import Invoice, InvoiceLine, Payment, FeeStructure
from apps.audit.services import log_audit_event


def generate_invoice_service(
    tenant,
    student_id,
    fee_structure_ids: list,
    due_date,
    discount_amount: Decimal = Decimal("0.00"),
    actor=None,
    request=None,
) -> Invoice:
    """
    Generates an invoice for a student based on selected fee structures transactionally.
    """
    structures = FeeStructure.objects.filter(tenant=tenant, id__in=fee_structure_ids)
    if not structures.exists():
        raise ValidationError("At least one valid fee structure must be selected.")

    with transaction.atomic():
        count = Invoice.objects.filter(tenant=tenant).count() + 1
        invoice_number = f"INV-{count:06d}"

        total_amount = sum((s.amount for s in structures), Decimal("0.00"))
        net_amount = max(Decimal("0.00"), total_amount - discount_amount)

        invoice = Invoice.objects.create(
            tenant=tenant,
            invoice_number=invoice_number,
            student_id=student_id,
            total_amount=total_amount,
            discount_amount=discount_amount,
            paid_amount=Decimal("0.00"),
            balance_amount=net_amount,
            status=Invoice.STATUS_ISSUED,
            due_date=due_date,
            created_by=actor,
        )

        for s in structures:
            InvoiceLine.objects.create(
                tenant=tenant,
                invoice=invoice,
                fee_structure=s,
                description=s.name,
                amount=s.amount,
                created_by=actor,
            )

        log_audit_event(
            action="CREATE",
            resource_type="Invoice",
            resource_id=str(invoice.id),
            tenant=tenant,
            actor=actor,
            description=f"Generated Invoice {invoice.invoice_number} for student {student_id}, total {net_amount}.",
            request=request,
        )

        return invoice


def record_payment_service(
    tenant,
    invoice_id,
    amount: Decimal,
    payment_method: str = Payment.METHOD_CASH,
    transaction_reference: str = "",
    idempotency_key: str = None,
    actor=None,
    request=None,
) -> Payment:
    """
    Transactionally records payment against an invoice with idempotency protection.
    Recalculates balance and updates status.
    """
    # 1. Idempotency Check
    if idempotency_key:
        existing = Payment.objects.filter(idempotency_key=idempotency_key).first()
        if existing:
            return existing

    amount = Decimal(str(amount))
    if amount <= Decimal("0.00"):
        raise ValidationError({"amount": "Payment amount must be greater than zero."})

    with transaction.atomic():
        # Lock the invoice row to prevent race conditions during concurrent payment submissions
        invoice = Invoice.objects.select_for_update().get(id=invoice_id, tenant=tenant)

        if invoice.status == Invoice.STATUS_PAID:
            raise ValidationError("This invoice has already been fully paid.")

        if amount > invoice.balance_amount:
            raise ValidationError({"amount": f"Payment amount ({amount}) exceeds outstanding balance ({invoice.balance_amount})."})

        count = Payment.objects.filter(tenant=tenant).count() + 1
        receipt_number = f"REC-{count:06d}"

        payment = Payment.objects.create(
            tenant=tenant,
            invoice=invoice,
            receipt_number=receipt_number,
            amount=amount,
            payment_method=payment_method,
            transaction_reference=transaction_reference,
            idempotency_key=idempotency_key,
            status=Payment.STATUS_SUCCESS,
            recorded_by=actor,
            created_by=actor,
        )

        # Update invoice balance and status
        invoice.paid_amount += amount
        invoice.balance_amount -= amount

        if invoice.balance_amount == Decimal("0.00"):
            invoice.status = Invoice.STATUS_PAID
        else:
            invoice.status = Invoice.STATUS_PARTIALLY_PAID

        invoice.save(update_fields=["paid_amount", "balance_amount", "status"])

        log_audit_event(
            action="CREATE",
            resource_type="Payment",
            resource_id=str(payment.id),
            tenant=tenant,
            actor=actor,
            description=f"Recorded payment of {amount} on invoice {invoice.invoice_number}. Receipt: {receipt_number}.",
            request=request,
        )

        return payment
