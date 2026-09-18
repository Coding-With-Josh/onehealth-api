from rest_framework.permissions import BasePermission

from .models import User, Hospital, HospitalStaffProfile


class IsPatient(BasePermission):
    """Request user is logged in AND is a patient (has a PatientProfile with a login)."""

    message = "Only patient accounts can perform this action."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.user_type == User.UserType.PATIENT
        )


class IsHospitalStaff(BasePermission):
    """Request user is logged in AND is any kind of hospital staff (doctor/nurse/admin)."""

    message = "Only hospital staff accounts can perform this action."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.user_type == User.UserType.HOSPITAL_STAFF
        )


class IsHospitalAdmin(BasePermission):
    """
    Narrower than IsHospitalStaff — only the hospital's own ADMIN role
    (not doctors/nurses) can manage staff or hospital-level settings.
    """

    message = "Only a hospital admin can perform this action."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        staff_profile = getattr(request.user, "staff_profile", None)
        return bool(staff_profile and staff_profile.role == HospitalStaffProfile.Role.ADMIN)


class IsDoctor(BasePermission):
    """
    Used specifically to gate the 'verify a medical record entry' action —
    that clinical-authority action must be restricted to doctors only,
    never nurses/admins, per the product decision.
    """

    message = "Only a doctor can perform this action."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        staff_profile = getattr(request.user, "staff_profile", None)
        return bool(staff_profile and staff_profile.role == HospitalStaffProfile.Role.DOCTOR)


class IsFromVerifiedHospital(BasePermission):
    """
    IMPORTANT SAFETY CHECK — a hospital staff account can technically
    exist while their hospital is still `pending` verification, or has
    since been `suspended`. This permission blocks any patient-data
    action (access requests, record creation, etc.) unless the staff
    member's hospital is currently VERIFIED.

    Apply this ALONGSIDE IsHospitalStaff on every endpoint that touches
    patient records — IsHospitalStaff alone is not enough.
    """

    message = "Your hospital's verification is not currently active."

    def has_permission(self, request, view):
        staff_profile = getattr(request.user, "staff_profile", None)
        if not staff_profile:
            return False
        return staff_profile.hospital.verification_status == Hospital.VerificationStatus.VERIFIED


class MustNotRequirePasswordChange(BasePermission):
    """
    Blocks EVERY action except the password-change endpoint itself while
    must_change_password=True. Prevents a staff member from skipping
    their forced temp-password reset and using the API with a
    system-generated password indefinitely.

    Apply this globally (see settings snippet) rather than per-view, so
    nobody forgets to add it to a new endpoint later.
    """

    message = "You must change your temporary password before continuing."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return True  # let auth-related permissions handle unauthenticated requests
        return not request.user.must_change_password
