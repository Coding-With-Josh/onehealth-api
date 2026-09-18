from django.contrib import admin
from django.core.exceptions import ValidationError

from .models import AccessGrant, AccessRequest, EmergencyContact, EmergencyEscalation


@admin.register(EmergencyContact)
class EmergencyContactAdmin(admin.ModelAdmin):
    list_display = ("full_name", "patient", "relationship", "phone_number", "priority_order", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("full_name", "patient__full_name", "phone_number", "email")
    readonly_fields = ("id", "response_token", "created_at")


@admin.register(AccessRequest)
class AccessRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "patient", "hospital", "request_type", "access_level", "status", "requested_by_staff", "created_at")
    list_filter = ("request_type", "access_level", "status", "hospital")
    search_fields = ("id", "patient__full_name", "hospital__name", "requested_by_staff__full_name")
    readonly_fields = ("id", "code", "created_at", "responded_at", "patient_response_deadline")

    def delete_model(self, request, obj):
        raise ValidationError("Access requests are historical records and should not be deleted.")


@admin.register(AccessGrant)
class AccessGrantAdmin(admin.ModelAdmin):
    list_display = ("id", "access_request", "access_level", "granted_by", "granted_at", "revoked_at", "revoked_by")
    list_filter = ("access_level", "granted_by", "revoked_by")
    search_fields = ("id", "access_request__patient__full_name", "access_request__hospital__name")
    readonly_fields = ("id", "access_request", "access_level", "granted_at", "granted_by", "revoked_at", "revoked_by")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(EmergencyEscalation)
class EmergencyEscalationAdmin(admin.ModelAdmin):
    list_display = ("id", "access_request", "stage", "triggered_at", "resolved_at", "resolved_by")
    list_filter = ("stage",)
    search_fields = ("id", "access_request__patient__full_name", "access_request__hospital__name", "resolved_by")
    readonly_fields = ("id", "access_request", "stage", "triggered_at", "resolved_at", "resolved_by")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
