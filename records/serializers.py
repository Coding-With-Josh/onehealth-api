from rest_framework import serializers

from .models import MedicalRecord


class MedicalRecordSerializer(serializers.ModelSerializer):
    # Read-only display names for the patient portal. Pure presentation:
    # the IDs remain the authoritative relations; these never accept input.
    hospital_name = serializers.CharField(source="hospital.name", read_only=True, allow_null=True)
    created_by_name = serializers.CharField(source="created_by_staff.full_name", read_only=True, allow_null=True)
    verified_by_name = serializers.CharField(source="verified_by_staff.full_name", read_only=True, allow_null=True)

    class Meta:
        model = MedicalRecord
        fields = [
            "id",
            "patient",
            "entry_type",
            "description",
            "verification_status",
            "verified_by_staff",
            "created_by_staff",
            "hospital",
            "visit",
            "supersedes_entry",
            "created_at",
            "hospital_name",
            "created_by_name",
            "verified_by_name",
        ]
        read_only_fields = [
            "id",
            "patient",
            "verification_status",
            "verified_by_staff",
            "created_by_staff",
            "hospital",
            "visit",
            "created_at",
        ]


class PatientMedicalRecordCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = MedicalRecord
        fields = ["entry_type", "description", "supersedes_entry"]

    def validate_supersedes_entry(self, value):
        patient = self.context["patient"]
        if value and value.patient_id != patient.id:
            raise serializers.ValidationError("You can only supersede one of your own records.")
        return value
