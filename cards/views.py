from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework import status

from core.audit import log_event
from core.responses import success_response
from users.permissions import IsFromVerifiedHospital, IsHospitalStaff, IsPatient
from users.models import HospitalStaffProfile

from .models import PatientCard
from .serializers import CardLookupSerializer, PatientCardSerializer


def patient_for_request(request):
    from users.models import PatientProfile
    return get_object_or_404(PatientProfile, user=request.user)


def staff_for_request(request):
    return get_object_or_404(HospitalStaffProfile.objects.select_related("hospital"), user=request.user)


def active_card_for_patient(patient):
    card = patient.cards.filter(status=PatientCard.Status.ACTIVE).order_by("-issued_at").first()
    if card and card.expires_at <= timezone.now():
        card.revoke()
        card = None
    return card


def _issue_card(request, patient):
    existing = active_card_for_patient(patient)
    if existing:
        return success_response(PatientCardSerializer(existing).data, "You already have an active patient card.")
    card = PatientCard.objects.create(patient=patient)
    log_event(
        "patient_card_issued", user_id=request.user, request=request,
        patient_id=patient.id, target_type="patient_card", target_id=card.id,
    )
    return success_response(PatientCardSerializer(card).data, "Patient card issued successfully.", status.HTTP_201_CREATED)


@swagger_auto_schema(
    method="post",
    tags=["Patient Cards"],
    operation_summary="Issue a patient card",
    operation_description="""
    Issues a new active patient card for the authenticated patient if they do not already have one.

    **Authentication:** Required.

    **Required Role:** Patient.
    """,
    security=[{"Bearer": []}],
    responses={
        201: openapi.Response(description="Patient card issued successfully")
    }
)
@api_view(["POST"])
@permission_classes([IsPatient])
def create_card(request):
    return _issue_card(request, patient_for_request(request))


@swagger_auto_schema(method="get", tags=["Patient Cards"], operation_summary="Get my patient card", operation_description="""Returns the authenticated patient's current active patient card.""", security=[{"Bearer": []}], responses={200: openapi.Response(description="Patient card retrieved successfully")})
@swagger_auto_schema(method="post", tags=["Patient Cards"], operation_summary="Issue or refresh a patient card", operation_description="""Issues a new patient card when no active card exists.""", security=[{"Bearer": []}], responses={201: openapi.Response(description="Patient card issued successfully")})
@api_view(["GET", "POST"])
@permission_classes([IsPatient])
def card(request):
    patient = patient_for_request(request)
    if request.method == "GET":
        active = active_card_for_patient(patient)
        return success_response(
            PatientCardSerializer(active).data if active else None,
            "Patient card retrieved successfully.",
        )
    return _issue_card(request, patient)


@swagger_auto_schema(
    method="post",
    tags=["Patient Cards"],
    operation_summary="Renew a patient card",
    operation_description="""
    Extends the authenticated patient's current active patient card.

    **Authentication:** Required.

    **Required Role:** Patient.
    """,
    security=[{"Bearer": []}],
    responses={
        200: openapi.Response(description="Patient card renewed successfully"),
        400: openapi.Response(description="No active patient card exists")
    }
)
@api_view(["POST"])
@permission_classes([IsPatient])
def renew_card(request):
    patient = patient_for_request(request)
    card = active_card_for_patient(patient)
    if not card:
        raise ValidationError({"card": "No active patient card exists. Issue a new card first."})
    card.renew()
    log_event(
        "patient_card_renewed", user_id=request.user, request=request,
        patient_id=patient.id, target_type="patient_card", target_id=card.id,
    )
    return success_response(PatientCardSerializer(card).data, "Patient card renewed successfully.")


@swagger_auto_schema(
    method="post",
    tags=["Patient Cards"],
    operation_summary="Revoke a patient card",
    operation_description="""
    Revokes the authenticated patient's active patient card.

    **Authentication:** Required.

    **Required Role:** Patient.
    """,
    security=[{"Bearer": []}],
    responses={
        200: openapi.Response(description="Patient card revoked successfully")
    }
)
@api_view(["POST"])
@permission_classes([IsPatient])
def revoke_card(request):
    patient = patient_for_request(request)
    card = get_object_or_404(PatientCard, patient=patient, status=PatientCard.Status.ACTIVE)
    card.revoke()
    log_event(
        "patient_card_revoked", user_id=request.user, request=request,
        patient_id=patient.id, target_type="patient_card", target_id=card.id,
    )
    return success_response(PatientCardSerializer(card).data, "Patient card revoked successfully.")


@swagger_auto_schema(
    method="post",
    tags=["Patient Cards"],
    operation_summary="Lookup a patient card",
    operation_description="""
    Identifies a patient using a patient card reference and confirms whether the card is valid.

    **Authentication:** Required.

    **Required Role:** Hospital Staff.
    """,
    security=[{"Bearer": []}],
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["card_reference"],
        properties={
            "card_reference": openapi.Schema(type=openapi.TYPE_STRING, description="Patient card reference code.")
        }
    ),
    responses={
        200: openapi.Response(description="Patient identified successfully"),
        400: openapi.Response(description="Card is invalid or expired")
    }
)
@api_view(["POST"])
@permission_classes([IsHospitalStaff, IsFromVerifiedHospital])
def lookup_card(request):
    staff = staff_for_request(request)
    serializer = CardLookupSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    card = get_object_or_404(
        PatientCard.objects.select_related("patient"),
        card_reference=serializer.validated_data["card_reference"],
        status=PatientCard.Status.ACTIVE,
    )
    if card.expires_at <= timezone.now():
        card.revoke()
        raise ValidationError({"card_reference": "This patient card has expired."})

    patient = card.patient
    log_event(
        "patient_card_lookup", user_id=request.user, request=request,
        patient_id=patient.id, hospital_id=staff.hospital_id,
        target_type="patient_card", target_id=card.id,
    )
    return success_response(
        {
            "patient_id": str(patient.id),
            "full_name": patient.full_name,
            "date_of_birth": patient.date_of_birth,
            "gender": patient.gender,
            "card_reference": card.card_reference,
            "card_expires_at": card.expires_at,
            "access_request_required": True,
        },
        "Patient identified successfully. An access request is still required to view the medical record.",
    )
