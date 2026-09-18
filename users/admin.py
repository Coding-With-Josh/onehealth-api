from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User, Hospital, HospitalStaffProfile, PatientProfile


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    """
    Extends Django's built-in UserAdmin so the admin site still gets its
    usual nice password-change widgets etc., just pointed at our fields
    instead of `username`.
    """

    ordering = ["email"]
    list_display = ["email", "user_type", "is_active", "must_change_password", "date_joined"]
    list_filter = ["user_type", "is_active", "must_change_password"]
    search_fields = ["email", "phone_number"]

    # Django's default UserAdmin fieldsets reference `username` — we
    # override completely rather than trying to patch around it.
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Account info", {"fields": ("user_type", "phone_number", "must_change_password")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser")}),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "user_type", "password1", "password2")}),
    )


@admin.register(Hospital)
class HospitalAdmin(admin.ModelAdmin):
    list_display = ["name", "registration_number", "verification_status", "created_at"]
    list_filter = ["verification_status"]
    search_fields = ["name", "registration_number"]
    # Verifying a hospital via the admin site (flip status to VERIFIED)
    # is a perfectly reasonable MVP verification workflow — a human
    # reviews it and clicks save. Automate this later if needed.


@admin.register(PatientProfile)
class PatientProfileAdmin(admin.ModelAdmin):
    list_display = ["full_name", "account_type", "guardian", "created_at"]
    list_filter = ["account_type"]
    search_fields = ["full_name"]


@admin.register(HospitalStaffProfile)
class HospitalStaffProfileAdmin(admin.ModelAdmin):
    list_display = ["full_name", "hospital", "role", "created_at"]
    list_filter = ["role", "hospital"]
    search_fields = ["full_name"]
