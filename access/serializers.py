from rest_framework import serializers

from .models import AccessGrant, AccessRequest, EmergencyContact, EmergencyEscalation


class AccessRequestSerializer(serializers.ModelSerializer):
    hospital_name = serializers.CharField(source="hospital.name", read_only=True)
    requested_by_staff_name = serializers.CharField(source="requested_by_staff.full_name", read_only=True)
    approval_code = serializers.CharField(source="code", read_only=True)

    class Meta:
        model = AccessRequest
        fields = [
            "id", "visit", "patient", "hospital", "hospital_name", "requested_by_staff",
            "requested_by_staff_name", "request_type", "access_level", "status", "approval_code",
            "created_at", "responded_at", "patient_response_deadline",
        ]
        read_only_fields = [
            "id", "patient", "hospital", "requested_by_staff", "status", "approval_code",
            "created_at", "responded_at", "patient_response_deadline",
        ]


class CreateAccessRequestSerializer(serializers.Serializer):
    visit = serializers.UUIDField()
    request_type = serializers.ChoiceField(choices=AccessRequest.RequestType.choices, default=AccessRequest.RequestType.NORMAL)
    access_level = serializers.ChoiceField(choices=AccessRequest.AccessLevel.choices, default=AccessRequest.AccessLevel.FULL_RECORD)


class AccessGrantSerializer(serializers.ModelSerializer):
    access_request = AccessRequestSerializer(read_only=True)
    is_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = AccessGrant
        fields = ["id", "access_request", "access_level", "granted_at", "granted_by", "revoked_at", "revoked_by", "is_active"]


class EmergencyContactSerializer(serializers.ModelSerializer):
    response_token = serializers.CharField(read_only=True)

    class Meta:
        model = EmergencyContact
        fields = ["id", "full_name", "relationship", "phone_number", "email", "priority_order", "response_token", "is_active", "created_at"]
        read_only_fields = ["id", "response_token", "created_at"]


class AccessDecisionSerializer(serializers.Serializer):
    code = serializers.CharField(min_length=6, max_length=6, required=True)


class EmergencyContactDecisionSerializer(serializers.Serializer):
    request_id = serializers.UUIDField(required=True)
    response_token = serializers.CharField(required=True)
    decision = serializers.ChoiceField(choices=["approve", "deny"], default="approve")


class EmergencyEscalationSerializer(serializers.ModelSerializer):
    access_request = AccessRequestSerializer(read_only=True)

    class Meta:
        model = EmergencyEscalation
        fields = ["id", "access_request", "stage", "triggered_at", "resolved_at", "resolved_by"]
