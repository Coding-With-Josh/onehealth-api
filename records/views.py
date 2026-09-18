from django.shortcuts import get_object_or_404
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied, ValidationError

from core.responses import success_response
from core.audit import log_event
from users.models import HospitalStaffProfile, PatientProfile, User
from visits.serializers import MedicationSerializer, VitalSerializer, VisitSerializer
from users.permissions import IsDoctor, IsFromVerifiedHospital, IsHospitalStaff, IsPatient

from .models import MedicalRecord
from .serializers import MedicalRecordSerializer, PatientMedicalRecordCreateSerializer


def patient_for_request(request):
    return get_object_or_404(PatientProfile, user=request.user)


def staff_for_request(request):
    return get_object_or_404(HospitalStaffProfile.objects.select_related("hospital"), user=request.user)


@swagger_auto_schema(method="get", tags=["Medical Records"], operation_summary="List my medical records", operation_description="""Returns all medical records associated with the authenticated patient.""", security=[{"Bearer": []}], responses={200: openapi.Response(description="Medical records retrieved successfully")})
@swagger_auto_schema(method="post", tags=["Medical Records"], operation_summary="Create a new medical record", operation_description="""Creates a new medical record entry for the authenticated patient.""", security=[{"Bearer": []}], request_body=openapi.Schema(type=openapi.TYPE_OBJECT, required=["entry_type", "description"], properties={"entry_type": openapi.Schema(type=openapi.TYPE_STRING, description="Entry type for the record."), "description": openapi.Schema(type=openapi.TYPE_STRING, description="Clinical description of the record.")}, responses={201: openapi.Response(description="Medical record added successfully")}))
@api_view(["GET", "POST"])
@permission_classes([IsPatient])
def my_records(request):
    patient = patient_for_request(request)
    if request.method == "GET":
        records = patient.medical_records.select_related(
            "verified_by_staff", "created_by_staff", "hospital", "visit", "supersedes_entry"
        )
        return success_response(MedicalRecordSerializer(records, many=True).data, "Medical records retrieved successfully.")

    serializer = PatientMedicalRecordCreateSerializer(data=request.data, context={"patient": patient})
    serializer.is_valid(raise_exception=True)
    record = serializer.save(patient=patient)
    return success_response(MedicalRecordSerializer(record).data, "Medical record added successfully.", status.HTTP_201_CREATED)


@swagger_auto_schema(
    method="post",
    tags=["Medical Records"],
    operation_summary="Verify a medical record",
    operation_description="""
    Verifies a patient's medical record as a doctor at the associated hospital.

    **Authentication:** Required.

    **Required Role:** Doctor.
    """,
    security=[{"Bearer": []}],
    responses={
        201: openapi.Response(description="Medical record verified successfully"),
        403: openapi.Response(description="Permission denied")
    }
)
@api_view(["POST"])
@permission_classes([IsDoctor, IsFromVerifiedHospital])
def verify_record(request, record_id):
    staff = staff_for_request(request)
    record = get_object_or_404(MedicalRecord, pk=record_id)

    if record.verification_status == MedicalRecord.VerificationStatus.DOCTOR_VERIFIED:
        return success_response(MedicalRecordSerializer(record).data, "Medical record is already doctor-verified.")

    verification_visit = record.visit
    if verification_visit:
        if verification_visit.hospital_id != staff.hospital_id or verification_visit.status != verification_visit.Status.ACTIVE:
            raise PermissionDenied("You can only verify records during an active visit at your hospital.")
    elif record.hospital_id:
        if record.hospital_id != staff.hospital_id:
            raise PermissionDenied("You can only verify records associated with your hospital.")
    else:
        # A patient-created entry has no hospital yet. It can be verified only
        # when the patient currently has an active visit at this doctor's hospital.
        verification_visit = record.patient.visits.filter(
            hospital_id=staff.hospital_id, status=record.patient.visits.model.Status.ACTIVE
        ).order_by("-admitted_at").first()
        if verification_visit is None:
            raise PermissionDenied("An active visit at your hospital is required to verify this record.")

    verified = MedicalRecord.objects.create(
        patient=record.patient,
        entry_type=record.entry_type,
        description=record.description,
        verification_status=MedicalRecord.VerificationStatus.DOCTOR_VERIFIED,
        verified_by_staff=staff,
        created_by_staff=record.created_by_staff,
        hospital=record.hospital or verification_visit.hospital,
        visit=verification_visit,
        supersedes_entry=record,
    )
    return success_response(MedicalRecordSerializer(verified).data, "Medical record verified successfully.", status.HTTP_201_CREATED)


@swagger_auto_schema(
    method="post",
    tags=["Medical Records"],
    operation_summary="Supersede an existing medical record",
    operation_description="""
    Creates a new medical record linked to an existing one without editing the original entry.

    **Authentication:** Required.
    """,
    security=[{"Bearer": []}],
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            "entry_type": openapi.Schema(type=openapi.TYPE_STRING, description="Optional new record type."),
            "description": openapi.Schema(type=openapi.TYPE_STRING, description="New clinical description for the superseding record.")
        }
    ),
    responses={
        201: openapi.Response(description="Medical record superseded successfully"),
        403: openapi.Response(description="Permission denied")
    }
)
@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def supersede_record(request, record_id):
    """Create a new record linked to an existing entry; never edit the original."""
    original = get_object_or_404(MedicalRecord, pk=record_id)
    entry_type = request.data.get("entry_type", original.entry_type)
    description = request.data.get("description")
    if not description:
        raise ValidationError({"description": "This field is required."})

    if request.user.user_type == User.UserType.PATIENT:
        patient = patient_for_request(request)
        if original.patient_id != patient.id or original.created_by_staff_id is not None:
            raise PermissionDenied("You can only supersede records you originally created as a patient.")
        record = MedicalRecord.objects.create(
            patient=patient,
            entry_type=entry_type,
            description=description,
            supersedes_entry=original,
        )
    else:
        staff = staff_for_request(request)
        if staff.hospital.verification_status != staff.hospital.VerificationStatus.VERIFIED:
            raise PermissionDenied("Your hospital's verification is not currently active.")
        if original.created_by_staff_id != staff.id:
            raise PermissionDenied("Only the staff member who created this record can supersede it.")
        record = MedicalRecord.objects.create(
            patient=original.patient,
            entry_type=entry_type,
            description=description,
            created_by_staff=staff,
            hospital=staff.hospital,
            visit=original.visit,
            supersedes_entry=original,
        )

    return success_response(MedicalRecordSerializer(record).data, "Medical record superseded successfully.", status.HTTP_201_CREATED)


@swagger_auto_schema(
    method="get",
    tags=["Medical Records"],
    operation_summary="Get my consolidated medical record",
    operation_description="""
    Returns the patient's complete medical record as a consolidated bundle of entries, visits, vitals, and medications.

    **Authentication:** Required.

    **Required Role:** Patient.
    """,
    security=[{"Bearer": []}],
    responses={
        200: openapi.Response(description="Medical record retrieved successfully")
    }
)
@api_view(["GET"])
@permission_classes([IsPatient])
def my_medical_record(request):
    """Return the patient's medical record as one coherent resource.

    The underlying data remains separated into append-only clinical entries,
    visits, vitals, and structured medications. This endpoint is a read-only
    convenience view for the patient app; it does not create a second source
    of truth.
    """
    patient = patient_for_request(request)
    records = patient.medical_records.select_related(
        "verified_by_staff", "created_by_staff", "hospital", "visit", "supersedes_entry"
    )
    standalone_entries = records.filter(visit__isnull=True)
    visits = patient.visits.select_related("hospital", "created_by_staff").prefetch_related(
        "vitals", "medications", "medical_records"
    )
    medications = patient.medications.select_related("visit", "prescribed_by_staff").filter(visit__isnull=True)
    return success_response(
        {
            "patient_id": str(patient.id),
            "entries": MedicalRecordSerializer(standalone_entries, many=True).data,
            "visits": [
                {
                    **VisitSerializer(visit).data,
                    "vitals": VitalSerializer(visit.vitals.all(), many=True).data,
                    "medications": MedicationSerializer(visit.medications.all(), many=True).data,
                    "clinical_entries": MedicalRecordSerializer(visit.medical_records.all(), many=True).data,
                }
                for visit in visits
            ],
            "medications": MedicationSerializer(medications, many=True).data,
        },
        "Medical record retrieved successfully.",
    )
