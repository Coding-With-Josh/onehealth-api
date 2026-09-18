from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied

from core.responses import success_response
from users.models import HospitalStaffProfile, PatientProfile, User
from .models import AuditLog
from .serializers import AuditLogSerializer


@swagger_auto_schema(
    method="get",
    tags=["Audit Logs"],
    operation_summary="List audit logs",
    operation_description="""
    Returns the audit records visible to the authenticated user according to their role.

    **Authentication:** Required.
    """,
    security=[{"Bearer": []}],
    responses={
        200: openapi.Response(description="Audit logs retrieved successfully")
    }
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def audit_logs(request):
    """Return only audit events the authenticated role is allowed to see."""
    user = request.user
    if user.user_type == User.UserType.PATIENT:
        patient = PatientProfile.objects.filter(user=user).first()
        if not patient:
            raise PermissionDenied("Patient profile not found.")
        logs = AuditLog.objects.filter(patient=patient)
    elif user.user_type == User.UserType.HOSPITAL_STAFF:
        staff = HospitalStaffProfile.objects.select_related("hospital").filter(user=user).first()
        if not staff:
            raise PermissionDenied("Hospital staff profile not found.")
        if staff.role != HospitalStaffProfile.Role.ADMIN:
            raise PermissionDenied("Only a hospital admin can view hospital audit logs.")
        logs = AuditLog.objects.filter(hospital=staff.hospital)
    elif user.user_type == User.UserType.PLATFORM_ADMIN:
        logs = AuditLog.objects.all()
    else:
        raise PermissionDenied("You do not have permission to view audit logs.")

    limit = min(max(int(request.query_params.get("limit", 50)), 1), 200)
    logs = logs.select_related("actor", "hospital", "patient")[:limit]
    return success_response(AuditLogSerializer(logs, many=True).data, "Audit logs retrieved successfully.")
