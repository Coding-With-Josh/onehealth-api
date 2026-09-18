from rest_framework import serializers

from .models import PatientCard


class PatientCardSerializer(serializers.ModelSerializer):
    is_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = PatientCard
        fields = [
            "id", "patient", "card_reference", "issued_at", "renewed_at",
            "expires_at", "status", "is_active",
        ]
        read_only_fields = [
            "id", "patient", "card_reference", "issued_at", "renewed_at",
            "expires_at", "status", "is_active",
        ]


class CardLookupSerializer(serializers.Serializer):
    card_reference = serializers.CharField(max_length=40)
