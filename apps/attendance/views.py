from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from apps.attendance.models import AttendanceRecord, AttendanceCorrectionRequest
from apps.attendance.serializers import (
    AttendanceRecordSerializer,
    BulkAttendanceSubmissionSerializer,
    AttendanceCorrectionRequestSerializer,
)
from apps.attendance.services import (
    bulk_mark_attendance_service,
    process_correction_request_service,
)
from apps.accounts.permissions import HasTenantPermission, IsTenantMember


class AttendanceRecordViewSet(viewsets.ModelViewSet):
    queryset = AttendanceRecord.objects.none()
    serializer_class = AttendanceRecordSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["section", "subject", "student", "date", "status"]

    def get_permissions(self):
        if self.action in ["create", "bulk_mark"]:
            return [HasTenantPermission("attendance.mark")()]
        return [HasTenantPermission("attendance.view")()]

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        if getattr(self, "swagger_fake_view", False) or not tenant:
            return AttendanceRecord.objects.none()
        return AttendanceRecord.objects.filter(tenant=tenant).select_related("student", "section")

    @action(detail=False, methods=["post"], url_path="bulk-mark")
    def bulk_mark(self, request):
        """
        Submits attendance in bulk for a class section.
        """
        serializer = BulkAttendanceSubmissionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        records = bulk_mark_attendance_service(
            tenant=request.tenant,
            section_id=data["section_id"],
            subject_id=data.get("subject_id"),
            date=data["date"],
            records=data["entries"],
            actor=request.user,
            request=request,
        )

        return Response(
            {
                "success": True,
                "message": f"Successfully marked attendance for {len(records)} students.",
                "data": {"count": len(records)},
            },
            status=status.HTTP_200_OK,
        )


class AttendanceCorrectionRequestViewSet(viewsets.ModelViewSet):
    queryset = AttendanceCorrectionRequest.objects.none()
    serializer_class = AttendanceCorrectionRequestSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["status", "requested_by"]

    def get_permissions(self):
        if self.action in ["approve", "reject"]:
            return [HasTenantPermission("attendance.correct")()]
        return [IsTenantMember()]

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        if getattr(self, "swagger_fake_view", False) or not tenant:
            return AttendanceCorrectionRequest.objects.none()
        return AttendanceCorrectionRequest.objects.filter(tenant=tenant).select_related("attendance_record__student")

    def perform_create(self, serializer):
        serializer.save(
            tenant=self.request.tenant,
            requested_by=self.request.user,
        )

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        correction = process_correction_request_service(
            tenant=request.tenant,
            correction_id=pk,
            approve=True,
            actor=request.user,
            request=request,
        )
        return Response({
            "success": True,
            "message": "Attendance correction request approved and applied.",
            "data": AttendanceCorrectionRequestSerializer(correction).data,
        })

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        correction = process_correction_request_service(
            tenant=request.tenant,
            correction_id=pk,
            approve=False,
            actor=request.user,
            request=request,
        )
        return Response({
            "success": True,
            "message": "Attendance correction request rejected.",
            "data": AttendanceCorrectionRequestSerializer(correction).data,
        })
