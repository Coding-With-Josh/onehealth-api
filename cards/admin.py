from django.contrib import admin
from .models import PatientCard


@admin.register(PatientCard)
class PatientCardAdmin(admin.ModelAdmin):
    list_display = ("card_reference", "patient", "status", "issued_at", "renewed_at", "expires_at")
    list_filter = ("status",)
    search_fields = ("card_reference", "patient__full_name", "patient__user__email")
    readonly_fields = ("id", "patient", "card_reference", "issued_at", "renewed_at", "expires_at", "status")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
