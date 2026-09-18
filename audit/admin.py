from django.contrib import admin
from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ["created_at", "action", "actor", "hospital", "patient", "target_type", "target_id"]
    list_filter = ["action", "hospital", "created_at"]
    search_fields = ["action", "target_type", "target_id", "actor__email"]
    readonly_fields = ["id", "actor", "hospital", "patient", "action", "target_type", "target_id", "metadata", "ip_address", "created_at"]
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False
