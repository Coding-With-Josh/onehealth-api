from rest_framework import serializers

from .models import Medication, Vital, Visit


class VisitSerializer(serializers.ModelSerializer):
    # Read-only display name for the patient portal. The `hospital` UUID
    # remains the authoritative relation; this never accepts input.
    hospital_name = serializers.CharField(source="hospital.name", read_only=True, allow_null=True)

    class Meta:
        model = Visit
        fields = [
            "id", "patient", "hospital", "hospital_name", "admitted_at",
            "checked_out_at", "checkout_requested_by_patient_at", "status",
            "created_by_staff",
        ]
        read_only_fields = ["id", "hospital", "admitted_at", "checked_out_at", "checkout_requested_by_patient_at", "status", "created_by_staff"]


class StartVisitSerializer(serializers.Serializer):
    patient = serializers.UUIDField()


class VitalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vital
        fields = [
            "id", "visit", "recorded_by_staff", "recorded_at",
            "blood_pressure_systolic", "blood_pressure_diastolic", "heart_rate",
            "temperature_c", "respiratory_rate", "oxygen_saturation",
            "weight_kg", "height_cm", "notes",
        ]
        read_only_fields = ["id", "visit", "recorded_by_staff", "recorded_at"]


class MedicationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Medication
        fields = [
            "id", "patient", "visit", "medication", "dose", "route", "frequency",
            "duration", "reason", "status", "prescribed_by_staff", "created_at",
        ]
        read_only_fields = ["id", "patient", "visit", "prescribed_by_staff", "created_at"]
