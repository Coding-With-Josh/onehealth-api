from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework import throttling
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated

from core.responses import success_response
from core.audit import log_event
from records.models import MedicalRecord
from records.serializers import MedicalRecordSerializer
from users.models import HospitalStaffProfile, PatientProfile, User
from users.permissions import IsFromVerifiedHospital, IsHospitalStaff, IsPatient
from visits.models import Visit

from .models import AccessGrant, AccessRequest, EmergencyContact, EmergencyEscalation
from .serializers import (
    AccessDecisionSerializer, AccessGrantSerializer, AccessRequestSerializer,
    CreateAccessRequestSerializer, EmergencyContactDecisionSerializer,
    EmergencyContactSerializer, EmergencyEscalationSerializer,
)


def patient_for_request(request):
    return get_object_or_404(PatientProfile, user=request.user)


class EmergencyContactResponseThrottle(throttling.AnonRateThrottle):
    scope = "emergency_contact_response"


def staff_for_request(request):
    return get_object_or_404(HospitalStaffProfile.objects.select_related("hospital"), user=request.user)


def create_grant(access_request, granted_by):
    grant, created = AccessGrant.objects.get_or_create(
        access_request=access_request,
        defaults={
            "access_level": access_request.access_level,
            "granted_by": granted_by,
        },
    )
    if not created and not grant.is_active:
        grant.revoked_at = None
        grant.revoked_by = None
        grant.granted_by = granted_by
        grant.granted_at = timezone.now()
        grant.save(update_fields=["revoked_at", "revoked_by", "granted_by", "granted_at"])
    access_request.status = AccessRequest.Status.APPROVED
    access_request.responded_at = timezone.now()
    access_request.save(update_fields=["status", "responded_at"])
    return grant


def revoke_visit_grants(visit, revoked_by=AccessGrant.RevokedBy.SYSTEM):
    for grant in AccessGrant.objects.select_related("access_request").filter(
        access_request__visit=visit, revoked_at__isnull=True
    ):
        grant.revoke(revoked_by)


@swagger_auto_schema(
    method="post",
    tags=["Access Requests"],
    operation_summary="Create an access request",
    operation_description="""
    Creates an access request for a patient record at the authenticated hospital.

    **Authentication:** Required.

    **Required Role:** Hospital Staff.
    """,
    security=[{"Bearer": []}],
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["visit", "request_type", "access_level"],
        properties={
            "visit": openapi.Schema(type=openapi.TYPE_STRING, description="Visit ID for the access request."),
            "request_type": openapi.Schema(type=openapi.TYPE_STRING, description="Request type, for example emergency or standard."),
            "access_level": openapi.Schema(type=openapi.TYPE_STRING, description="Requested access level."),
        },
        example={
            "visit": "d5f1d0dd-1b9b-4b0d-879d-5ff6b53df0ff",
            "request_type": "routine",
            "access_level": "limited"
        }
    ),
    responses={
        201: openapi.Response(description="Access request created successfully"),
        400: openapi.Response(description="Invalid request payload"),
        403: openapi.Response(description="Permission denied")
    }
)
@api_view(["POST"])
@permission_classes([IsHospitalStaff, IsFromVerifiedHospital])
def create_access_request(request):
    staff = staff_for_request(request)
    serializer = CreateAccessRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    visit = get_object_or_404(Visit.objects.select_related("patient", "hospital"), pk=serializer.validated_data["visit"])
    if visit.hospital_id != staff.hospital_id:
        raise PermissionDenied("You can only request access for visits at your hospital.")
    if visit.status != Visit.Status.ACTIVE:
        raise ValidationError({"visit": "Access can only be requested for an active visit."})
    if AccessRequest.objects.filter(visit=visit, status=AccessRequest.Status.PENDING).exists():
        raise ValidationError({"visit": "This visit already has a pending access request."})

    access_request = AccessRequest.objects.create(
        visit=visit,
        patient=visit.patient,
        hospital=staff.hospital,
        requested_by_staff=staff,
        request_type=serializer.validated_data["request_type"],
        access_level=serializer.validated_data["access_level"],
    )
    # Emergency requests enter the escalation state machine. Normal access
    # requests simply expire if the patient does not respond.
    if access_request.request_type == AccessRequest.RequestType.EMERGENCY:
        EmergencyEscalation.objects.create(
            access_request=access_request,
            stage=EmergencyEscalation.Stage.PATIENT_NOTIFIED,
        )
    log_event("access_request_created", user_id=request.user, request=request, patient_id=access_request.patient_id,
              hospital_id=access_request.hospital_id, target_type="access_request", target_id=access_request.id,
              request_type=access_request.request_type, access_level=access_request.access_level)
    return success_response(
        AccessRequestSerializer(access_request).data,
        "Access request created successfully.",
        status.HTTP_201_CREATED,
    )


@swagger_auto_schema(
    method="get",
    tags=["Access Requests"],
    operation_summary="List my access requests",
    operation_description="""
    Returns access requests associated with the authenticated patient.

    **Authentication:** Required.

    **Required Role:** Patient.
    """,
    security=[{"Bearer": []}],
    responses={
        200: openapi.Response(description="Access requests retrieved successfully")
    }
)
@api_view(["GET"])
@permission_classes([IsPatient])
def my_access_requests(request):
    patient = patient_for_request(request)
    requests = patient.access_requests.select_related("hospital", "requested_by_staff", "visit")
    return success_response(AccessRequestSerializer(requests, many=True).data, "Access requests retrieved successfully.")


@swagger_auto_schema(
    method="post",
    tags=["Access Requests"],
    operation_summary="Approve an access request",
    operation_description="""
    Approves a pending access request using the patient-provided code.

    **Authentication:** Required.

    **Required Role:** Patient.
    """,
    security=[{"Bearer": []}],
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["code"],
        properties={
            "code": openapi.Schema(type=openapi.TYPE_STRING, description="Approval code issued with the access request.")
        },
        example={"code": "482195"}
    ),
    responses={
        201: openapi.Response(description="Access approved successfully"),
        400: openapi.Response(description="Incorrect approval code"),
        403: openapi.Response(description="Permission denied")
    }
)
@api_view(["POST"])
@permission_classes([IsPatient])
def approve_access_request(request, request_id):
    patient = patient_for_request(request)
    access_request = get_object_or_404(AccessRequest.objects.select_related("visit", "hospital"), pk=request_id, patient=patient)
    if access_request.status != AccessRequest.Status.PENDING:
        raise ValidationError({"status": "This access request is no longer pending."})
    serializer = AccessDecisionSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    if serializer.validated_data["code"] != access_request.code:
        raise ValidationError({"code": "Invalid approval code."})
    grant = create_grant(access_request, AccessGrant.GrantedBy.PATIENT)
    if hasattr(access_request, "escalation") and access_request.escalation.resolved_at is None:
        access_request.escalation.resolve("patient")
    log_event("access_request_approved", user_id=request.user, request=request, patient_id=access_request.patient_id,
              hospital_id=access_request.hospital_id, target_type="access_grant", target_id=grant.id,
              granted_by=AccessGrant.GrantedBy.PATIENT)
    return success_response(AccessGrantSerializer(grant).data, "Access approved successfully.", status.HTTP_201_CREATED)


@swagger_auto_schema(
    method="post",
    tags=["Access Requests"],
    operation_summary="Deny an access request",
    operation_description="""
    Denies a pending access request from a hospital.

    **Authentication:** Required.

    **Required Role:** Patient.
    """,
    security=[{"Bearer": []}],
    responses={
        200: openapi.Response(description="Access request denied successfully"),
        403: openapi.Response(description="Permission denied")
    }
)
@api_view(["POST"])
@permission_classes([IsPatient])
def deny_access_request(request, request_id):
    patient = patient_for_request(request)
    access_request = get_object_or_404(AccessRequest, pk=request_id, patient=patient)
    if access_request.status != AccessRequest.Status.PENDING:
        raise ValidationError({"status": "This access request is no longer pending."})
    access_request.status = AccessRequest.Status.DENIED
    access_request.responded_at = timezone.now()
    access_request.save(update_fields=["status", "responded_at"])
    if hasattr(access_request, "escalation") and access_request.escalation.resolved_at is None:
        access_request.escalation.resolve("patient")
    log_event("access_request_denied", user_id=request.user, request=request, patient_id=access_request.patient_id,
              hospital_id=access_request.hospital_id, target_type="access_request", target_id=access_request.id)
    return success_response(AccessRequestSerializer(access_request).data, "Access request denied successfully.")


@swagger_auto_schema(
    method="get",
    tags=["Access Grants"],
    operation_summary="List active access grants",
    operation_description="""
    Returns all active grants available to the authenticated patient or verified hospital staff member.

    **Authentication:** Required.
    """,
    security=[{"Bearer": []}],
    responses={
        200: openapi.Response(description="Active access grants retrieved successfully")
    }
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def active_grants(request):
    if request.user.user_type == User.UserType.PATIENT:
        patient = patient_for_request(request)
        grants = AccessGrant.objects.select_related("access_request__hospital", "access_request__visit").filter(
            access_request__patient=patient, revoked_at__isnull=True
        )
    elif request.user.user_type == User.UserType.HOSPITAL_STAFF:
        staff = staff_for_request(request)
        if staff.hospital.verification_status != staff.hospital.VerificationStatus.VERIFIED:
            raise PermissionDenied("Your hospital's verification is not currently active.")
        grants = AccessGrant.objects.select_related("access_request__patient", "access_request__visit").filter(
            access_request__hospital=staff.hospital, revoked_at__isnull=True
        )
    else:
        raise PermissionDenied("Only patients and hospital staff can view active access grants.")
    grants = [grant for grant in grants if grant.is_active]
    return success_response(AccessGrantSerializer(grants, many=True).data, "Active access grants retrieved successfully.")


@swagger_auto_schema(
    method="post",
    tags=["Access Grants"],
    operation_summary="Revoke an access grant",
    operation_description="""
    Revokes a previously approved access grant for the authenticated patient.

    **Authentication:** Required.

    **Required Role:** Patient.
    """,
    security=[{"Bearer": []}],
    responses={
        200: openapi.Response(description="Access grant revoked successfully"),
        403: openapi.Response(description="Permission denied")
    }
)
@api_view(["POST"])
@permission_classes([IsPatient])
def revoke_grant(request, grant_id):
    patient = patient_for_request(request)
    grant = get_object_or_404(AccessGrant.objects.select_related("access_request"), pk=grant_id)
    if grant.access_request.patient_id != patient.id:
        raise PermissionDenied("You can only revoke your own access grants.")
    grant.revoke(AccessGrant.RevokedBy.PATIENT)
    log_event("access_grant_revoked", user_id=request.user, request=request, patient_id=grant.access_request.patient_id,
              hospital_id=grant.access_request.hospital_id, target_type="access_grant", target_id=grant.id)
    return success_response(AccessGrantSerializer(grant).data, "Access grant revoked successfully.")


@swagger_auto_schema(
    method="get",
    tags=["Hospital Patients"],
    operation_summary="View a patient profile within an active access grant",
    operation_description="""
    Retrieves a patient's profile details for a hospital staff member who has an active grant.

    **Authentication:** Required.

    **Required Role:** Hospital Staff.
    """,
    security=[{"Bearer": []}],
    responses={
        200: openapi.Response(description="Patient profile retrieved successfully"),
        403: openapi.Response(description="Active access grant required")
    }
)
@api_view(["GET"])
@permission_classes([IsHospitalStaff, IsFromVerifiedHospital])
def hospital_patient_profile(request, patient_id):
    staff = staff_for_request(request)
    patient = get_object_or_404(PatientProfile, pk=patient_id)
    if not AccessGrant.objects.filter(
        access_request__patient=patient,
        access_request__hospital=staff.hospital,
        revoked_at__isnull=True,
        access_request__visit__status=Visit.Status.ACTIVE,
    ).exists():
        raise PermissionDenied("An active access grant is required to view this patient's information.")
    log_event("patient_profile_viewed", user_id=request.user, request=request, patient_id=patient.id,
              hospital_id=staff.hospital_id, target_type="patient", target_id=patient.id)
    data = {
        "id": str(patient.id),
        "full_name": patient.full_name,
        "date_of_birth": patient.date_of_birth,
        "gender": patient.gender,
        "blood_type": patient.blood_type,
        "genotype": patient.genotype,
        "residential_address": patient.residential_address,
    }
    return success_response(data, "Patient profile retrieved successfully.")


@swagger_auto_schema(method="get", tags=["Hospital Patients"], operation_summary="List a patient's records", operation_description="""Retrieves a patient's clinical records when the staff member has an active access grant.""", security=[{"Bearer": []}], responses={200: openapi.Response(description="Patient records retrieved successfully")})
@swagger_auto_schema(method="post", tags=["Hospital Patients"], operation_summary="Add a record to a patient's chart", operation_description="""Adds a clinical record for a patient within an active hospital visit.""", security=[{"Bearer": []}], request_body=openapi.Schema(type=openapi.TYPE_OBJECT, required=["entry_type", "description"], properties={"entry_type": openapi.Schema(type=openapi.TYPE_STRING, description="Clinical entry type."), "description": openapi.Schema(type=openapi.TYPE_STRING, description="Clinical note or record description.")}, responses={201: openapi.Response(description="Patient medical record added successfully"), 403: openapi.Response(description="Permission denied")}))
@api_view(["GET", "POST"])
@permission_classes([IsHospitalStaff, IsFromVerifiedHospital])
def hospital_patient_records(request, patient_id):
    staff = staff_for_request(request)
    patient = get_object_or_404(PatientProfile, pk=patient_id)
    grant = AccessGrant.objects.filter(
        access_request__patient=patient,
        access_request__hospital=staff.hospital,
        revoked_at__isnull=True,
        access_request__visit__status=Visit.Status.ACTIVE,
    ).select_related("access_request").order_by("-granted_at").first()
    if not grant:
        raise PermissionDenied("An active access grant is required to access this patient's records.")

    if request.method == "GET":
        records = patient.medical_records.select_related("verified_by_staff", "created_by_staff", "hospital", "visit", "supersedes_entry")
        if grant.access_level == AccessRequest.AccessLevel.CRITICAL_INFO_ONLY:
            records = records.filter(entry_type__in=["allergy", "condition", "medication"])
        log_event("patient_records_viewed", user_id=request.user, request=request, patient_id=patient.id,
                  hospital_id=staff.hospital_id, target_type="patient", target_id=patient.id,
                  access_level=grant.access_level)
        return success_response(MedicalRecordSerializer(records, many=True).data, "Patient records retrieved successfully.")

    if grant.access_level == AccessRequest.AccessLevel.CRITICAL_INFO_ONLY:
        raise PermissionDenied("Critical-information-only access cannot be used to add clinical records.")
    if not request.data.get("entry_type") or not request.data.get("description"):
        raise ValidationError({"entry_type": "This field is required.", "description": "This field is required."})
    visit = grant.access_request.visit
    if visit.status != Visit.Status.ACTIVE:
        raise PermissionDenied("The care episode is no longer active.")
    record = MedicalRecord.objects.create(
        patient=patient,
        entry_type=request.data["entry_type"],
        description=request.data["description"],
        created_by_staff=staff,
        hospital=staff.hospital,
        visit=visit,
    )
    return success_response(MedicalRecordSerializer(record).data, "Patient medical record added successfully.", status.HTTP_201_CREATED)


@swagger_auto_schema(
    method="get",
    tags=["Access Grants"],
    operation_summary="List active grants for the hospital",
    operation_description="""
    Returns all currently active access grants for the authenticated hospital staff's hospital.

    **Authentication:** Required.

    **Required Role:** Hospital Staff.
    """,
    security=[{"Bearer": []}],
    responses={
        200: openapi.Response(description="Hospital active access grants retrieved successfully")
    }
)
@api_view(["GET"])
@permission_classes([IsHospitalStaff, IsFromVerifiedHospital])
def hospital_active_grants(request):
    staff = staff_for_request(request)
    grants = AccessGrant.objects.select_related("access_request__patient", "access_request__visit").filter(
        access_request__hospital=staff.hospital, revoked_at__isnull=True
    )
    grants = [grant for grant in grants if grant.is_active]
    return success_response(AccessGrantSerializer(grants, many=True).data, "Hospital active access grants retrieved successfully.")


@swagger_auto_schema(method="get", tags=["Emergency Contacts"], operation_summary="List emergency contacts", operation_description="""Returns the authenticated patient's active emergency contacts.""", security=[{"Bearer": []}], responses={200: openapi.Response(description="Emergency contacts retrieved successfully")})
@swagger_auto_schema(method="post", tags=["Emergency Contacts"], operation_summary="Add an emergency contact", operation_description="""Adds a new emergency contact for the authenticated patient.""", security=[{"Bearer": []}], request_body=openapi.Schema(type=openapi.TYPE_OBJECT, required=["full_name", "relationship", "phone_number"], properties={"full_name": openapi.Schema(type=openapi.TYPE_STRING, description="Emergency contact full name."), "relationship": openapi.Schema(type=openapi.TYPE_STRING, description="Relationship to the patient."), "phone_number": openapi.Schema(type=openapi.TYPE_STRING, description="Emergency contact phone number."), "priority_order": openapi.Schema(type=openapi.TYPE_INTEGER, description="Priority order for the contact.")}, responses={201: openapi.Response(description="Emergency contact added successfully"), 400: openapi.Response(description="Invalid contact details")}) )
@api_view(["GET", "POST"])
@permission_classes([IsPatient])
def emergency_contacts(request):
    patient = patient_for_request(request)
    if request.method == "GET":
        contacts = patient.emergency_contacts.filter(is_active=True)
        return success_response(EmergencyContactSerializer(contacts, many=True).data, "Emergency contacts retrieved successfully.")
    if patient.emergency_contacts.filter(is_active=True).count() >= getattr(settings, "MAX_EMERGENCY_CONTACTS", 5):
        raise ValidationError({"non_field_errors": ["The maximum number of emergency contacts has been reached."]})
    serializer = EmergencyContactSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    priority = serializer.validated_data.get("priority_order")
    if "priority_order" not in request.data:
        priority = patient.emergency_contacts.filter(is_active=True).count() + 1
    contact = serializer.save(patient=patient, priority_order=priority)
    log_event("emergency_contact_added", user_id=request.user, request=request, patient_id=patient.id,
              target_type="emergency_contact", target_id=contact.id)
    return success_response(EmergencyContactSerializer(contact).data, "Emergency contact added successfully.", status.HTTP_201_CREATED)


@swagger_auto_schema(
    method="delete",
    tags=["Emergency Contacts"],
    operation_summary="Remove an emergency contact",
    operation_description="""
    Deactivates an emergency contact for the authenticated patient.

    **Authentication:** Required.

    **Required Role:** Patient.
    """,
    security=[{"Bearer": []}],
    responses={
        200: openapi.Response(description="Emergency contact removed successfully")
    }
)
@api_view(["DELETE"])
@permission_classes([IsPatient])
def delete_emergency_contact(request, contact_id):
    patient = patient_for_request(request)
    contact = get_object_or_404(EmergencyContact, pk=contact_id, patient=patient)
    contact.is_active = False
    contact.save(update_fields=["is_active"])
    log_event("emergency_contact_removed", user_id=request.user, request=request, patient_id=patient.id,
              target_type="emergency_contact", target_id=contact.id)
    return success_response(None, "Emergency contact removed successfully.")


@swagger_auto_schema(
    method="post",
    tags=["Emergency Contacts"],
    operation_summary="Respond to an emergency-contact escalation",
    operation_description="""
    Allows a registered emergency contact to approve or deny an emergency access request using the supplied response token.

    **Authentication:** Not required.
    """,
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["request_id", "response_token", "decision"],
        properties={
            "request_id": openapi.Schema(type=openapi.TYPE_STRING, description="Access request identifier."),
            "response_token": openapi.Schema(type=openapi.TYPE_STRING, description="Emergency contact response token."),
            "decision": openapi.Schema(type=openapi.TYPE_STRING, description="Either approve or deny.")
        }
    ),
    responses={
        200: openapi.Response(description="Emergency access response processed successfully"),
        403: openapi.Response(description="Invalid or unauthorized emergency response")
    }
)
@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([EmergencyContactResponseThrottle])
def emergency_contact_respond(request, contact_id):
    serializer = EmergencyContactDecisionSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    contact = get_object_or_404(
        EmergencyContact,
        pk=contact_id,
        response_token=serializer.validated_data["response_token"],
        is_active=True,
    )
    access_request = get_object_or_404(
        AccessRequest.objects.select_related("patient", "visit"),
        pk=serializer.validated_data["request_id"],
    )
    if access_request.patient_id != contact.patient_id:
        raise PermissionDenied("This emergency contact is not authorized for this patient.")
    if access_request.status != AccessRequest.Status.PENDING:
        raise ValidationError({"status": "This access request is no longer pending."})
    escalation = get_object_or_404(EmergencyEscalation, access_request=access_request)
    if escalation.stage != EmergencyEscalation.Stage.EMERGENCY_CONTACT_NOTIFIED:
        raise PermissionDenied("This request has not yet been escalated to an emergency contact.")

    if serializer.validated_data["decision"] == "deny":
        access_request.status = AccessRequest.Status.DENIED
        access_request.responded_at = timezone.now()
        access_request.save(update_fields=["status", "responded_at"])
        escalation.resolve(contact.full_name)
        log_event("emergency_access_denied", request=request, patient_id=access_request.patient_id,
                  hospital_id=access_request.hospital_id, target_type="access_request", target_id=access_request.id,
                  responder_type="emergency_contact")
        return success_response(AccessRequestSerializer(access_request).data, "Emergency access denied successfully.")

    grant = create_grant(access_request, AccessGrant.GrantedBy.EMERGENCY_CONTACT)
    escalation.resolve(contact.full_name)
    log_event("emergency_access_approved", request=request, patient_id=access_request.patient_id,
              hospital_id=access_request.hospital_id, target_type="access_grant", target_id=grant.id,
              responder_type="emergency_contact")
    return success_response(AccessGrantSerializer(grant).data, "Emergency access approved successfully.", status.HTTP_201_CREATED)


@swagger_auto_schema(
    method="get",
    tags=["Emergency Escalations"],
    operation_summary="Get escalation details",
    operation_description="""
    Returns the current status of an emergency escalation for the authorized patient, staff member, or contact.

    **Authentication:** Required.
    """,
    security=[{"Bearer": []}],
    responses={
        200: openapi.Response(description="Escalation status retrieved successfully"),
        403: openapi.Response(description="You are not involved in this escalation")
    }
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def escalation_detail(request, escalation_id):
    escalation = get_object_or_404(EmergencyEscalation.objects.select_related("access_request__patient", "access_request__hospital", "access_request__requested_by_staff"), pk=escalation_id)
    allowed = False
    if request.user.user_type == User.UserType.PATIENT:
        allowed = escalation.access_request.patient.user_id == request.user.id
    elif request.user.user_type == User.UserType.HOSPITAL_STAFF:
        staff = staff_for_request(request)
        allowed = staff.hospital_id == escalation.access_request.hospital_id
    else:
        # Emergency contacts use their secure response token on the action endpoint;
        # no standing platform-admin access is granted here.
        allowed = False
    if not allowed:
        raise PermissionDenied("You are not involved in this escalation.")
    return success_response(EmergencyEscalationSerializer(escalation).data, "Escalation status retrieved successfully.")


def process_escalations():
    now = timezone.now()
    created = 0
    contacts_notified = 0
    timeout = getattr(settings, "EMERGENCY_CONTACT_RESPONSE_TIMEOUT_MINUTES", 15)
    pending = AccessRequest.objects.filter(status=AccessRequest.Status.PENDING, visit__status=Visit.Status.ACTIVE).select_related("patient", "hospital")
    for access_request in pending:
        if access_request.patient_response_deadline and access_request.patient_response_deadline > now:
            continue
        if access_request.request_type != AccessRequest.RequestType.EMERGENCY:
            access_request.status = AccessRequest.Status.EXPIRED
            access_request.responded_at = now
            access_request.save(update_fields=["status", "responded_at"])
            log_event("access_request_expired", patient_id=access_request.patient_id, hospital_id=access_request.hospital_id,
                      target_type="access_request", target_id=access_request.id)
            continue
        escalation = getattr(access_request, "escalation", None)
        if escalation is None:
            escalation = EmergencyEscalation.objects.create(
                access_request=access_request,
                stage=EmergencyEscalation.Stage.PATIENT_NOTIFIED,
            )
        if escalation.resolved_at is not None:
            continue
        if escalation.stage == EmergencyEscalation.Stage.PATIENT_NOTIFIED:
            escalation.stage = EmergencyEscalation.Stage.EMERGENCY_CONTACT_NOTIFIED
            escalation.triggered_at = now
            escalation.save(update_fields=["stage", "triggered_at"])
            created += 1
            contacts_notified += access_request.patient.emergency_contacts.filter(is_active=True).count()
            log_event("emergency_access_escalated", patient_id=access_request.patient_id, hospital_id=access_request.hospital_id,
                      target_type="emergency_escalation", target_id=escalation.id)
    return created, contacts_notified
