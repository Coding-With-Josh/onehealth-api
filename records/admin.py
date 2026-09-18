from django.contrib import admin
from django.core.exceptions import ValidationError

from .models import MedicalRecord


@admin.register(MedicalRecord)
class MedicalRecordAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "patient",
        "entry_type",
        "verification_status",
        "hospital",
        "visit",
        "created_by_staff",
        "verified_by_staff",
        "created_at",
    )
    list_filter = ("verification_status", "entry_type", "hospital")
    search_fields = (
        "id",
        "patient__full_name",
        "entry_type",
        "description",
    )
    readonly_fields = ("id", "created_at")

    def save_model(self, request, obj, form, change):
        if change:
            raise ValidationError("Medical records are append-only and cannot be edited.")
        super().save_model(request, obj, form, change)

    def delete_model(self, request, obj):
        raise ValidationError("Medical records are append-only and cannot be deleted.")
