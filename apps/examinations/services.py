"""
Examination Domain Services: Publishing workflow and Marks validation.
"""
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from apps.examinations.models import Exam, Mark
from apps.audit.services import log_audit_event


def publish_exam_results_service(tenant, exam_id, actor, request=None) -> Exam:
    """
    Publishes examination results and freezes marks against further unauthorized modifications.
    """
    with transaction.atomic():
        exam = Exam.objects.select_for_update().get(id=exam_id, tenant=tenant)

        if exam.is_published:
            raise ValidationError("This examination has already been published.")

        # Ensure all marks are approved before publishing
        unapproved_count = Mark.objects.filter(
            exam_subject__exam=exam,
            status__in=[Mark.STATUS_DRAFT, Mark.STATUS_SUBMITTED],
        ).count()

        if unapproved_count > 0:
            # Auto-approve remaining marks upon principal publication
            Mark.objects.filter(exam_subject__exam=exam).update(status=Mark.STATUS_APPROVED)

        exam.is_published = True
        exam.published_at = timezone.now()
        exam.published_by = actor
        exam.status = Exam.STATUS_COMPLETED
        exam.save(update_fields=["is_published", "published_at", "published_by", "status"])

        log_audit_event(
            action="PUBLISH",
            resource_type="Exam",
            resource_id=str(exam.id),
            tenant=tenant,
            actor=actor,
            description=f"Results published for exam '{exam.name}'. Marks are now immutable.",
            request=request,
        )

        return exam
