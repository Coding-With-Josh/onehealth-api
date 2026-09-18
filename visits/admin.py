from django.contrib import admin
from django.core.exceptions import ValidationError

from .models import Medication, Vital, Visit


@admin.register(Visit)
class VisitAdmin(admin.ModelAdmin):
    list_display = ("id", "patient", "hospital", "status", "admitted_at", "checked_out_at", "created_by_staff")
    list_filter = ("status", "hospital")
    search_fields = ("id", "patient__full_name", "hospital__name", "created_by_staff__full_name")
    readonly_fields = ("id", "admitted_at", "checked_out_at", "checkout_requested_by_patient_at")


@admin.register(Vital)
class VitalAdmin(admin.ModelAdmin):
    list_display = ("id", "visit", "recorded_by_staff", "recorded_at", "heart_rate", "oxygen_saturation")
    list_filter = ("recorded_by_staff__hospital",)
    search_fields = ("id", "visit__patient__full_name", "recorded_by_staff__full_name")
    readonly_fields = ("id", "recorded_at")

    def save_model(self, request, obj, form, change):
        if change:
            raise ValidationError("Vitals are append-only and cannot be edited.")
        super().save_model(request, obj, form, change)

    def delete_model(self, request, obj):
        raise ValidationError("Vitals are append-only and cannot be deleted.")


@admin.register(Medication)
class MedicationAdmin(admin.ModelAdmin):
    list_display = ("id", "patient", "medication", "dose", "frequency", "status", "prescribed_by_staff", "created_at")
    list_filter = ("status", "prescribed_by_staff__hospital")
    search_fields = ("id", "patient__full_name", "medication", "reason")
    readonly_fields = ("id", "created_at")

    def save_model(self, request, obj, form, change):
        if change:
            raise ValidationError("Medication records are append-only and cannot be edited.")
        super().save_model(request, obj, form, change)

    def delete_model(self, request, obj):
        raise ValidationError("Medication records are append-only and cannot be deleted.")
