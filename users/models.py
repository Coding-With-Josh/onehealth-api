import uuid

from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken
from .managers import CustomUserManager


class User(AbstractBaseUser, PermissionsMixin):
    """
    The ONLY table that can actually log in to the platform.

    IMPORTANT: We are NOT using Django's built-in User model. That model
    hard-codes `username` as the login field and has no concept of
    "what kind of account is this" — both of which we need. Instead we
    build our own minimal account model and attach a *profile* model to
    it depending on what kind of user it is (see PatientProfile /
    HospitalStaffProfile below).

    Think of CustomUser as "can this person log in, and as what role" —
    nothing medical or hospital-specific belongs on this model.
    """

    class UserType(models.TextChoices):
        PATIENT = "patient", "Patient"
        HOSPITAL_STAFF = "hospital_staff", "Hospital Staff"
        PLATFORM_ADMIN = "platform_admin", "Platform Admin"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # UUID instead of auto-increment int: prevents anyone from guessing
    # "user id 1, 2, 3..." and probing the API for valid accounts —
    # matters a lot for a medical records system.

    email = models.EmailField(unique=True, db_index=True)
    phone_number = models.CharField(max_length=20, unique=True)

    user_type = models.CharField(max_length=20, choices=UserType.choices)

    is_active = models.BooleanField(
        default=True,
        help_text="Unchecking this disables login WITHOUT deleting the account or its data.",
    )
    is_staff = models.BooleanField(
        default=False,
        help_text="Django admin site access only — unrelated to hospital staff.",
    )

    # Set True the moment a hospital-staff account is created by an admin
    # with a system-generated temporary password. Forces a password change
    # before they can do anything else. See views.ChangePasswordView.
    must_change_password = models.BooleanField(default=False)

    date_joined = models.DateTimeField(default=timezone.now)

    objects = CustomUserManager()

    USERNAME_FIELD = "email"   # log in with email, not username
    REQUIRED_FIELDS = []       # no extra fields required for createsuperuser besides email/password

    def __str__(self):
        return f"{self.email} ({self.user_type})"

    def auth_tokens(self):
        refresh = RefreshToken.for_user(self)

        # update last login date
        self.last_login = timezone.now()
        self.save()
        
        return {
            "access": str(refresh.access_token),
            "refresh": str(refresh)
        }


class Hospital(models.Model):
    """
    An organization, NOT a user. Nobody logs in "as a hospital" — staff
    members log in individually and are linked to a Hospital via
    HospitalStaffProfile. This model just holds the institution's own
    identity + verification status.
    """

    class VerificationStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        VERIFIED = "verified", "Verified"
        REJECTED = "rejected", "Rejected"
        SUSPENDED = "suspended", "Suspended"
        # SUSPENDED covers the edge case we flagged earlier: a hospital's
        # registration later lapses/gets revoked. Don't delete the row,
        # just flip status — keeps historical records intact.

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    name = models.CharField(max_length=255)
    registration_number = models.CharField(
        max_length=100,
        unique=True,
        help_text="National Health Facility Registry ID — the source of truth we verify against.",
    )
    phermc_number = models.CharField(max_length=100, blank=True)
    cac_number = models.CharField(max_length=100, blank=True)

    address = models.CharField(max_length=500, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    verification_status = models.CharField(
        max_length=20, choices=VerificationStatus.choices, default=VerificationStatus.PENDING
    )
    verified_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class PatientProfile(models.Model):
    """
    Medical-identity data for a patient. Deliberately separate from
    CustomUser because NOT every patient profile has a login:

    - A self-managed adult patient: has a `user` (their own CustomUser).
    - A dependent (child): `user` is NULL. Access is entirely through
      `guardian` instead. This is what lets us register a newborn
      without needing an email for them.
    - A community-enrolled patient (elderly/non-literate, onboarded by
      a doctor at an outreach event): may or may not have a `user`
      depending on whether they end up with their own login later.
      `enrolled_by_staff` records which staff member created it, for
      the consent/accountability trail we discussed.
    """

    class AccountType(models.TextChoices):
        SELF_MANAGED = "self_managed", "Self Managed"
        DEPENDENT = "dependent", "Dependent"
        COMMUNITY_ENROLLED = "community_enrolled", "Community Enrolled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Nullable on purpose — see docstring above.
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, null=True, blank=True, related_name="patient_profile"
    )

    full_name = models.CharField(max_length=255)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=20, blank=True)
    blood_type = models.CharField(max_length=5, blank=True)

    account_type = models.CharField(max_length=20, choices=AccountType.choices)

    # Only set when account_type == DEPENDENT. Points at the guardian's
    # OWN PatientProfile (a guardian is a patient too, with extra rights
    # over this row). Enforced in serializers/validators, not the DB,
    # since Django doesn't easily support conditional-required FKs.
    guardian = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="dependents"
    )

    # Only set when account_type == COMMUNITY_ENROLLED — which staff
    # member created this profile on the patient's behalf. Doubles as
    # part of the consent/audit trail for that enrollment path.
    enrolled_by_staff = models.ForeignKey(
        "HospitalStaffProfile", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.full_name


class HospitalStaffProfile(models.Model):
    """
    A staff member belonging to a Hospital. Always has a `user` —
    unlike PatientProfile, staff always log in individually (nobody
    acts "on behalf of" hospital staff the way a guardian does for a
    dependent).
    """

    class Role(models.TextChoices):
        DOCTOR = "doctor", "Doctor"
        NURSE = "nurse", "Nurse"
        ADMIN = "admin", "Hospital Admin"
        # ADMIN = the account that manages the hospital's own account
        # (adds/removes staff). Distinct from PLATFORM_ADMIN on CustomUser,
        # which is US (the company), not the hospital.

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="staff_profile")
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE, related_name="staff")

    full_name = models.CharField(max_length=255)
    role = models.CharField(max_length=20, choices=Role.choices)

    # Required for doctors specifically — this is what lets a DOCTOR
    # (and only a doctor) mark a medical record entry as "verified"
    # elsewhere in the system. Kept optional at the DB level because
    # nurses/admins won't have one, validated per-role in the serializer.
    professional_license_number = models.CharField(max_length=100, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.full_name} — {self.hospital.name} ({self.role})"
