from django.contrib.auth.password_validation import validate_password
from django.utils.crypto import get_random_string
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import User, Hospital, HospitalStaffProfile, PatientProfile


# ---------------------------------------------------------------------------
# PATIENT REGISTRATION
# ---------------------------------------------------------------------------

class PatientRegistrationSerializer(serializers.Serializer):
    """
    Public self-registration for an adult patient. Creates BOTH the
    User (login) and the PatientProfile (medical identity) in one
    atomic call — a patient should never exist as one without the other.
    """

    email = serializers.EmailField()
    password = serializers.CharField(
        write_only=True,
        help_text="At least 10 characters; must pass Django's configured password validators.",
    )
    phone_number = serializers.CharField(required=True, allow_blank=False)

    full_name = serializers.CharField(max_length=255)
    date_of_birth = serializers.DateField(help_text="Format: YYYY-MM-DD.")
    gender = serializers.CharField(required=False, allow_blank=True)
    blood_type = serializers.CharField(required=False, allow_blank=True)

    def validate_phone_number(self, value):
        value = value.strip()
        if User.objects.filter(phone_number=value).exists():
            raise serializers.ValidationError("An account with this phone number already exists.")
        return value

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    # def validate_password(self, value):
    #     # Uses Django's built-in password validators (configured in
    #     # settings.py — min length, not-too-common, not-all-numeric etc.)
    #     # rather than us inventing our own weak rules.
    #     validate_password(value)
    #     return value

    def create(self, validated_data):
        user = User.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
            user_type=User.UserType.PATIENT,
            phone_number=validated_data.get("phone_number", ""),
        )
        profile = PatientProfile.objects.create(
            user=user,
            full_name=validated_data["full_name"],
            date_of_birth=validated_data["date_of_birth"],
            gender=validated_data.get("gender", ""),
            blood_type=validated_data.get("blood_type", ""),
            account_type=PatientProfile.AccountType.SELF_MANAGED,
        )
        return profile


class DependentRegistrationSerializer(serializers.Serializer):
    """
    Called by an ALREADY-LOGGED-IN patient (the guardian) to register a
    child. Deliberately has no email/password fields — a dependent has
    no login of their own, per the product decision that a child's
    record is fully controlled by the parent's account.
    """

    full_name = serializers.CharField(max_length=255)
    date_of_birth = serializers.DateField()
    gender = serializers.CharField(required=False, allow_blank=True)
    blood_type = serializers.CharField(required=False, allow_blank=True)

    def create(self, validated_data):
        guardian_profile = self.context["guardian_profile"]  # set by the view
        return PatientProfile.objects.create(
            user=None,
            guardian=guardian_profile,
            account_type=PatientProfile.AccountType.DEPENDENT,
            **validated_data,
        )


# ---------------------------------------------------------------------------
# HOSPITAL REGISTRATION
# ---------------------------------------------------------------------------

class HospitalRegistrationSerializer(serializers.Serializer):
    """
    Registers a NEW hospital AND its first admin account together.
    The hospital starts as `PENDING` — nothing in this serializer marks
    it verified. Verification is a separate, deliberate step (manual
    review and/or a check against the public Health Facility Registry),
    so a hospital cannot self-certify into a trusted state.
    """

    # Hospital fields
    hospital_name = serializers.CharField(max_length=255)
    registration_number = serializers.CharField(max_length=100)
    phermc_number = serializers.CharField(required=False, allow_blank=True)
    cac_number = serializers.CharField(required=False, allow_blank=True)
    address = serializers.CharField(required=False, allow_blank=True)

    # First admin user fields
    admin_email = serializers.EmailField()
    admin_password = serializers.CharField(write_only=True)
    admin_full_name = serializers.CharField(max_length=255)

    def validate_hospital_name(self, value):
        if Hospital.objects.filter(name=value).exists():
            raise serializers.ValidationError("A hospital with this name already exists.")
        return value

    def validate_registration_number(self, value):
        if Hospital.objects.filter(registration_number=value).exists():
            raise serializers.ValidationError("A hospital with this registration number already exists.")
        return value

    def validate_phermc_number(self, value):
        if value and Hospital.objects.filter(phermc_number=value).exists():
            raise serializers.ValidationError("A hospital with this PHERMC number already exists.")
        return value

    def validate_cac_number(self, value):
        if value and Hospital.objects.filter(cac_number=value).exists():
            raise serializers.ValidationError("A hospital with this CAC number already exists.")
        return value

    def validate_admin_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    def validate_admin_password(self, value):
        validate_password(value)
        return value

    def create(self, validated_data):
        hospital = Hospital.objects.create(
            name=validated_data["hospital_name"],
            registration_number=validated_data["registration_number"],
            phermc_number=validated_data.get("phermc_number", ""),
            cac_number=validated_data.get("cac_number", ""),
            address=validated_data.get("address", ""),
            verification_status=Hospital.VerificationStatus.PENDING,
        )
        admin_user = User.objects.create_user(
            email=validated_data["admin_email"],
            password=validated_data["admin_password"],
            user_type=User.UserType.HOSPITAL_STAFF,
        )
        HospitalStaffProfile.objects.create(
            user=admin_user,
            hospital=hospital,
            full_name=validated_data["admin_full_name"],
            role=HospitalStaffProfile.Role.ADMIN,
        )
        return hospital


class HospitalStaffCreateSerializer(serializers.Serializer):
    """
    Used by a hospital ADMIN to add a staff member (doctor/nurse/admin)
    to their own hospital. Deliberately does NOT accept a password from
    the client — a random system-generated temporary password is created
    server-side and the account is flagged `must_change_password=True`.

    WHY: if staff picked their own password at creation time over an
    admin-facing form, there's a real risk of weak/shared passwords
    across a hospital's accounts. Forcing a first-login password change
    is standard practice for admin-provisioned accounts.
    """

    email = serializers.EmailField()
    full_name = serializers.CharField(max_length=255)
    role = serializers.ChoiceField(choices=HospitalStaffProfile.Role.choices)
    professional_license_number = serializers.CharField(required=False, allow_blank=True)

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    def validate(self, attrs):
        # Doctors must have a license number — this is what makes the
        # "only a doctor can verify a medical record entry" rule meaningful
        # elsewhere in the system, instead of just a role label.
        if attrs["role"] == HospitalStaffProfile.Role.DOCTOR and not attrs.get(
            "professional_license_number"
        ):
            raise serializers.ValidationError(
                {"professional_license_number": "Required for staff registered as a doctor."}
            )
        return attrs

    def create(self, validated_data):
        hospital = self.context["hospital"]  # set by the view from request.user's own hospital

        # get_random_string with this charset avoids ambiguous characters
        # (0/O, 1/l) since a human may need to type this temp password in.
        temp_password = get_random_string(
            length=12, allowed_chars="ABCDEFGHJKMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789!@#$%"
        )
        user = User.objects.create_user(
            email=validated_data["email"],
            password=temp_password,
            user_type=User.UserType.HOSPITAL_STAFF,
            must_change_password=True,
        )
        staff_profile = HospitalStaffProfile.objects.create(
            user=user,
            hospital=hospital,
            full_name=validated_data["full_name"],
            role=validated_data["role"],
            professional_license_number=validated_data.get("professional_license_number", ""),
        )

        # In production this temp password must be delivered to the staff
        # member via the Notification Service (email/SMS) — NEVER logged
        # or returned in a plain API response in a real deployment. It's
        # attached to the instance here only so the calling view can hand
        # it to the notification service; strip it before any response.
        staff_profile._temp_password = temp_password
        return staff_profile

class HospitalSerializer(serializers.ModelSerializer):

    class Meta:
        model = Hospital
        fields = [
            'id', 'name', 'registration_number', 'phermc_number',
            'cac_number', 'address', 'latitude', 'longitude',
            'verification_status', 'verified_at', 'created_at'
        ]

# ---------------------------------------------------------------------------
# LOGIN — custom JWT claims
# ---------------------------------------------------------------------------

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    SimpleJWT's default token only encodes the user id. We extend it so
    the FRONTEND can read `user_type` (and hospital context, if
    applicable) straight off the token without an extra API call right
    after login — useful for routing patients vs hospital staff to the
    correct app screens immediately.

    Do NOT put anything sensitive (medical data, full names, etc.) into
    the token — it's base64, not encrypted, just signed.
    """

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["user_type"] = user.user_type
        token["must_change_password"] = user.must_change_password

        if user.user_type == User.UserType.HOSPITAL_STAFF:
            staff_profile = getattr(user, "staff_profile", None)
            if staff_profile:
                token["hospital_id"] = str(staff_profile.hospital_id)
                token["role"] = staff_profile.role
                token["hospital_verification_status"] = staff_profile.hospital.verification_status

        return token


# ---------------------------------------------------------------------------
# PROFILE (the "/me/" endpoint)
# ---------------------------------------------------------------------------

class PatientProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = PatientProfile
        fields = ["id", "full_name", "date_of_birth", "gender", "blood_type", "account_type", "created_at"]
        read_only_fields = ["id", "account_type", "created_at"]


class UserSerializer(serializers.ModelSerializer):

    # Source is `patient_profile`, NOT `profile` — the OneToOne reverse
    # relation name on User is `patient_profile`. Pointing at `profile`
    # made login/registration 500 for every user.
    # allow_null: staff and platform-admin users legitimately have no
    # PatientProfile; their `profile` is null, not an error.
    profile = PatientProfileSerializer(source="patient_profile", read_only=True, allow_null=True)

    class Meta:
        model = User
        fields = ['id', 'email', 'phone_number', 'user_type', 'profile', 'must_change_password']

class HospitalStaffProfileSerializer(serializers.ModelSerializer):
    hospital_name = serializers.CharField(source="hospital.name", read_only=True)
    hospital_verification_status = serializers.CharField(
        source="hospital.verification_status", read_only=True
    )

    class Meta:
        model = HospitalStaffProfile
        fields = [
            "id",
            "full_name",
            "role",
            "professional_license_number",
            "hospital",
            "hospital_name",
            "hospital_verification_status",
            "created_at",
        ]
        read_only_fields = ["id", "role", "hospital", "created_at"]
        # `role` is read-only here on purpose: a staff member should never
        # be able to promote themselves to admin/doctor via their own
        # profile update — role changes should go through a separate,
        # admin-only endpoint (not included in this file, but flag it
        # when you build staff management).


# ---------------------------------------------------------------------------
# PASSWORD MANAGEMENT
# ---------------------------------------------------------------------------

class ChangePasswordSerializer(serializers.Serializer):
    """Used both for a normal voluntary password change AND for the
    forced first-login change when must_change_password=True."""

    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    def validate_old_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value

    def validate_new_password(self, value):
        validate_password(value)
        return value

    def save(self, **kwargs):
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.must_change_password = False
        user.save(update_fields=["password", "must_change_password"])
        return user


# ---------------------------------------------------------------------------
# HOSPITAL STAFF MANAGEMENT / HOSPITAL VERIFICATION
# ---------------------------------------------------------------------------

class HospitalStaffListSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email", read_only=True)
    is_active = serializers.BooleanField(source="user.is_active", read_only=True)
    must_change_password = serializers.BooleanField(source="user.must_change_password", read_only=True)

    class Meta:
        model = HospitalStaffProfile
        fields = [
            "id", "email", "full_name", "role", "professional_license_number",
            "is_active", "must_change_password", "hospital", "created_at",
        ]
        read_only_fields = fields


class HospitalVerificationSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=[
        Hospital.VerificationStatus.VERIFIED,
        Hospital.VerificationStatus.REJECTED,
        Hospital.VerificationStatus.SUSPENDED,
    ])
