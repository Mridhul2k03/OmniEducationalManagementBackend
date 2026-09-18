"""
Attendance Domain Services: Bulk Marking and Correction Approval Workflow.
"""
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from apps.attendance.models import AttendanceRecord, AttendanceCorrectionRequest
from apps.enrollments.models import Enrollment
from apps.audit.services import log_audit_event


def bulk_mark_attendance_service(
    tenant,
    section_id,
    date,
    records: list,
    subject_id=None,
    actor=None,
    request=None,
) -> list:
    """
    Validates and marks attendance for multiple enrolled students in a batch.
    Transactionally handles creation and updates without duplicate errors.
    """
    # Verify section belongs to tenant
    enrolled_student_ids = set(
        Enrollment.objects.filter(
            tenant=tenant,
            section_id=section_id,
            status=Enrollment.STATUS_ACTIVE,
        ).values_list("student_id", flat=True)
    )

    created_or_updated = []
    with transaction.atomic():
        for item in records:
            student_id = item.get("student_id")
            if student_id not in enrolled_student_ids:
                continue

            status_val = item.get("status", AttendanceRecord.STATUS_PRESENT)
            remarks = item.get("remarks", "")

            record, created = AttendanceRecord.objects.update_or_create(
                tenant=tenant,
                student_id=student_id,
                section_id=section_id,
                subject_id=subject_id,
                date=date,
                defaults={
                    "status": status_val,
                    "remarks": remarks,
                    "marked_by": actor,
                },
            )
            created_or_updated.append(record)

        log_audit_event(
            action="UPDATE" if not created else "CREATE",
            resource_type="AttendanceRecord",
            resource_id=f"{section_id}_{date}",
            tenant=tenant,
            actor=actor,
            description=f"Marked attendance for {len(created_or_updated)} students on {date}.",
            request=request,
        )

    return created_or_updated


def process_correction_request_service(
    tenant,
    correction_id,
    approve: bool,
    actor,
    request=None,
) -> AttendanceCorrectionRequest:
    """
    Approves or rejects an attendance correction request.
    If approved, applies change to original attendance record and audits it.
    """
    with transaction.atomic():
        correction = AttendanceCorrectionRequest.objects.select_for_update().get(
            id=correction_id,
            tenant=tenant,
        )

        if correction.status != AttendanceCorrectionRequest.STATUS_PENDING:
            raise ValidationError("This correction request has already been reviewed.")

        correction.reviewed_by = actor
        correction.reviewed_at = timezone.now()

        if approve:
            correction.status = AttendanceCorrectionRequest.STATUS_APPROVED
            record = correction.attendance_record
            old_status = record.status
            record.status = correction.requested_status
            record.save(update_fields=["status"])

            log_audit_event(
                action="APPROVE",
                resource_type="AttendanceCorrectionRequest",
                resource_id=str(correction.id),
                tenant=tenant,
                actor=actor,
                changes={"before": {"status": old_status}, "after": {"status": record.status}},
                description=f"Attendance corrected for {record.student.full_name} from {old_status} to {record.status}.",
                request=request,
            )
        else:
            correction.status = AttendanceCorrectionRequest.STATUS_REJECTED
            log_audit_event(
                action="REJECT",
                resource_type="AttendanceCorrectionRequest",
                resource_id=str(correction.id),
                tenant=tenant,
                actor=actor,
                description=f"Attendance correction request {correction.id} was rejected.",
                request=request,
            )

        correction.save(update_fields=["status", "reviewed_by", "reviewed_at"])
        return correction
