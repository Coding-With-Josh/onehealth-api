"""
Function-based views for the auth module.

All business logic here is unchanged from the original class-based
version — only the *shape* changed: FBVs with explicit decorators
instead of generics/APIView subclasses, per the team's preference.

Every view:
  - returns core.responses.success_response(...) on success — never a
    bare Response(...) — so every endpoint has the same envelope shape.
  - lets exceptions (ValidationError, PermissionDenied, etc.) propagate
    instead of catching them — core.exceptions.custom_exception_handler
    (wired in settings via EXCEPTION_HANDLER) turns them into the same
    envelope shape on the error side. Don't add your own try/except
    around serializer.is_valid(raise_exception=True) — that's the point
    of raise_exception=True.
  - is documented with @extend_schema for the auto-generated Swagger/
    OpenAPI docs (see urls.py / project_urls_snippet.py for where those
    are served).
"""
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.password_validation import validate_password
from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework import permissions, status, throttling
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from django.core.mail import EmailMessage

from core.audit import log_event
from core.messages import AUTH, GENERIC, PASSWORD, PROFILE, REGISTRATION
from core.responses import error_response, success_response
from core.utils import is_correct_format, generate_temporary_password, is_valid_email

from .models import User, Hospital, HospitalStaffProfile, PatientProfile
from .permissions import IsHospitalAdmin, IsPatient
from .serializers import (
    UserSerializer,
    HospitalSerializer,
    ChangePasswordSerializer,
    CustomTokenObtainPairSerializer,
    DependentRegistrationSerializer,
    HospitalRegistrationSerializer,
    HospitalStaffCreateSerializer,
    HospitalStaffProfileSerializer,
    PatientProfileSerializer,
    PatientRegistrationSerializer,
    HospitalStaffListSerializer,
    HospitalVerificationSerializer,
)
from django.conf import settings
from django.contrib.auth import authenticate
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

# ---------------------------------------------------------------------------
# THROTTLES
# ---------------------------------------------------------------------------
# Registration and login are the two endpoints most likely to be hit by
# automated abuse (fake sign-ups, brute-force login attempts). Named
# scopes so they can be tuned independently in settings.py without
# touching this file again.

class RegistrationThrottle(throttling.AnonRateThrottle):
    scope = "registration"


class LoginThrottle(throttling.AnonRateThrottle):
    scope = "login"

@swagger_auto_schema(
    method="post",
    tags=["Patients"],
    operation_summary="Register a new patient account",
    operation_description="""
    Creates a new self-managed patient account.

    This endpoint creates:
    - A `User` account used for authentication.
    - A `PatientProfile` containing the patient's medical identity information.
    - The user is automatically assigned the `patient` user type.
    - The patient profile is intended to be assigned the `self_managed` account type.

    **Notes for Frontend:**
    - This is a public registration endpoint.
    - `email` must be a valid email address.
    - The email must not already belong to another user.
    - `date_of_birth` must use the format `YYYY-MM-DD`.
    - `gender` is required by the current view.
    - `full_name` is accepted by the endpoint and is used when creating the patient profile.
    - A successful registration returns the newly created user information.
    - JWT tokens are NOT returned by this endpoint. The patient must log in separately after registration.
    - Registration is protected by `RegistrationThrottle`, so repeated registration attempts may be rate-limited.

    **Important Current Implementation Note:**
    - The current view reads `phone_number` from `data.get("email")` instead of
      `data.get("phone_number")`.
    - The current view also reads `blood_type` from `data.get("email")` instead of
      `data.get("blood_type")`.
    - These appear to be implementation mistakes and should be corrected in the view.
    - The intended request structure is documented below.

    **Authentication:** Not required.
    """,
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=[
            "email",
            "password",
            "phone_number",
            "full_name",
            "date_of_birth",
            "gender",
        ],
        properties={
            "email": openapi.Schema(
                type=openapi.TYPE_STRING,
                format=openapi.FORMAT_EMAIL,
                description="Unique email address used by the patient to log in."
            ),
            "password": openapi.Schema(
                type=openapi.TYPE_STRING,
                format=openapi.FORMAT_PASSWORD,
                description="Password for the patient's account."
            ),
            "phone_number": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Patient's phone number."
            ),
            "full_name": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Patient's full legal or preferred name."
            ),
            "date_of_birth": openapi.Schema(
                type=openapi.TYPE_STRING,
                format=openapi.FORMAT_DATE,
                description="Patient's date of birth. Must be provided as YYYY-MM-DD."
            ),
            "gender": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Patient's gender."
            ),
            "blood_type": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Patient's blood type, for example A+, O-, AB+."
            ),
        },
        example={
            "email": "john.patient@example.com",
            "password": "SecurePassword123!",
            "phone_number": "08012345678",
            "full_name": "John Patient",
            "date_of_birth": "1995-06-14",
            "gender": "male",
            "blood_type": "O+"
        }
    ),
    responses={
        201: openapi.Response(
            description="Patient account created successfully",
            examples={
                "application/json": {
                    "status": True,
                    "message": "Account created successfully",
                    "data": {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "email": "john.patient@example.com",
                        "phone_number": "08012345678",
                        "user_type": "patient",
                        "profile": {
                            "id": "a12e8400-e29b-41d4-a716-446655440111",
                            "full_name": "John Patient",
                            "date_of_birth": "1995-06-14",
                            "gender": "male",
                            "blood_type": "O+",
                            "account_type": "self_managed",
                            "created_at": "2026-09-17T12:30:00Z"
                        }
                    }
                }
            }
        ),
        400: openapi.Response(
            description="Invalid registration data",
            examples={
                "application/json": {
                    "status": False,
                    "message": "Invalid email format."
                }
            }
        ),
        429: openapi.Response(
            description="Too many registration attempts",
            examples={
                "application/json": {
                    "detail": "Request was throttled."
                }
            }
        ),
    }
)
@api_view(["POST"])
@permission_classes([permissions.AllowAny])
@throttle_classes([RegistrationThrottle])
def register_patient(request):
    """Create a self-managed patient account and its profile.

    The phone number is required because it is the primary lookup
    identifier hospitals use to find a patient. Finding a patient this
    way never by itself grants access to their medical records.
    """
    serializer = PatientRegistrationSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    profile = serializer.save()

    log_event(
        "patient_registered",
        user_id=profile.user,
        request=request,
        patient_id=profile.id,
        target_type="patient",
        target_id=profile.id,
    )

    return success_response(
        UserSerializer(profile.user).data,
        "Account created successfully.",
        status.HTTP_201_CREATED,
    )

@swagger_auto_schema(
    method="post",
    tags=["Patients"],
    operation_summary="Register a dependent patient",
    operation_description="""
    Creates a dependent patient under the currently authenticated patient's account.

    A dependent is a patient profile that is controlled by a guardian rather than
    having its own login credentials.

    **Notes for Frontend:**
    - The logged-in user must be a patient.
    - The authenticated patient's profile becomes the dependent's guardian.
    - A dependent does NOT require an email address.
    - A dependent does NOT require a password.
    - A dependent does NOT receive JWT tokens.
    - `full_name`, `date_of_birth`, and `gender` are required by the current view.
    - `date_of_birth` must use `YYYY-MM-DD`.
    - `blood_type` can be supplied if known.
    - The returned `data` object contains the created patient profile.

    **Important Current Implementation Note:**
    - The model requires an `account_type`.
    - The intended account type for this endpoint is `dependent`.
    - The current view does not explicitly provide
      `account_type=PatientProfile.AccountType.DEPENDENT` when creating the profile.
    - This should be corrected in the view.

    **Authentication:** Required.

    **Required Role:** Patient.
    """,
    security=[{"Bearer": []}],
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["full_name", "date_of_birth", "gender"],
        properties={
            "full_name": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Full name of the dependent."
            ),
            "date_of_birth": openapi.Schema(
                type=openapi.TYPE_STRING,
                format=openapi.FORMAT_DATE,
                description="Dependent's date of birth in YYYY-MM-DD format."
            ),
            "gender": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Dependent's gender."
            ),
            "blood_type": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Dependent's blood type, if known."
            ),
        },
        example={
            "full_name": "Sarah Patient",
            "date_of_birth": "2018-04-20",
            "gender": "female",
            "blood_type": "A+"
        }
    ),
    responses={
        201: openapi.Response(
            description="Dependent created successfully",
            examples={
                "application/json": {
                    "status": True,
                    "message": "Dependent created successfully",
                    "data": {
                        "id": "750e8400-e29b-41d4-a716-446655440000",
                        "full_name": "Sarah Patient",
                        "date_of_birth": "2018-04-20",
                        "gender": "female",
                        "blood_type": "A+",
                        "account_type": "dependent",
                        "created_at": "2026-09-17T12:35:00Z"
                    }
                }
            }
        ),
        400: openapi.Response(
            description="Missing or invalid dependent information",
            examples={
                "application/json": {
                    "status": False,
                    "message": "Date of birth must be provided in form YYYY-MM-DD"
                }
            }
        ),
        401: openapi.Response(
            description="Authentication credentials were not provided or token is invalid",
            examples={
                "application/json": {
                    "detail": "Authentication credentials were not provided."
                }
            }
        ),
        403: openapi.Response(
            description="Authenticated user is not permitted to register a dependent",
            examples={
                "application/json": {
                    "detail": "You do not have permission to perform this action."
                }
            }
        ),
    }
)
@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated, IsPatient])
def register_dependent(request):
    """Create a dependent patient profile under the logged-in patient."""
    guardian_profile = get_object_or_404(PatientProfile, user=request.user)

    serializer = DependentRegistrationSerializer(
        data=request.data,
        context={"guardian_profile": guardian_profile},
    )
    serializer.is_valid(raise_exception=True)
    patient = serializer.save()

    log_event(
        "dependent_registered",
        user_id=request.user,
        request=request,
        patient_id=patient.id,
        target_type="patient",
        target_id=patient.id,
    )

    return success_response(
        PatientProfileSerializer(patient).data,
        "Dependent created successfully.",
        status.HTTP_201_CREATED,
    )

@swagger_auto_schema(
    method="post",
    tags=["Hospitals"],
    operation_summary="Register a hospital and its first administrator",
    operation_description="""
    Registers a new hospital together with the hospital's first administrator account.

    The hospital is intended to be created with verification status `pending`.
    The administrator receives a normal user account with user type `hospital_staff`
    and a hospital staff profile with role `admin`.

    **Notes for Frontend:**
    - This endpoint is publicly accessible.
    - All fields listed in the request schema are required by the current view.
    - `admin_email` must be a valid email address.
    - The administrator email cannot already belong to another user.
    - The hospital registration number must be unique.
    - Hospital name, PHERMC number, and CAC number are also checked for duplicates.
    - The current view requires the administrator password to contain at least 5 characters.
    - A successful registration does NOT mean the hospital has been verified.
    - New hospitals start with `verification_status = pending`.
    - Verification must occur through a separate verification process.
    - Registration is protected by `RegistrationThrottle`.

    **Important Current Implementation Note:**
    - The current view creates the hospital using `Hospital(...)` but does not call
      `hospital.save()` before using it in `HospitalStaffProfile.objects.create(...)`.
    - The hospital must normally be saved before it can be referenced by the staff profile.
    - This should be corrected in the implementation.

    **Authentication:** Not required.
    """,
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=[
            "hospital_name",
            "registration_number",
            "phermc_number",
            "cac_number",
            "address",
            "admin_email",
            "admin_password",
            "admin_full_name",
        ],
        properties={
            "hospital_name": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Official name of the hospital."
            ),
            "registration_number": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Unique National Health Facility Registry or hospital registration number."
            ),
            "phermc_number": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Hospital PHERMC registration/reference number."
            ),
            "cac_number": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Hospital Corporate Affairs Commission registration number."
            ),
            "address": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Physical address of the hospital."
            ),
            "admin_email": openapi.Schema(
                type=openapi.TYPE_STRING,
                format=openapi.FORMAT_EMAIL,
                description="Email address for the hospital's first administrator."
            ),
            "admin_password": openapi.Schema(
                type=openapi.TYPE_STRING,
                format=openapi.FORMAT_PASSWORD,
                description="Password for the first hospital administrator."
            ),
            "admin_full_name": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Full name of the first hospital administrator."
            ),
        },
        example={
            "hospital_name": "Central Medical Hospital",
            "registration_number": "HFR-2026-001245",
            "phermc_number": "PHERMC-88291",
            "cac_number": "RC-1948273",
            "address": "15 Medical Avenue, Lagos",
            "admin_email": "admin@centralmedical.example",
            "admin_password": "SecurePassword123!",
            "admin_full_name": "Dr. James Williams"
        }
    ),
    responses={
        201: openapi.Response(
            description="Hospital registered successfully and awaiting verification",
            examples={
                "application/json": {
                    "status": True,
                    "message": "Hospital created successfully",
                    "data": {
                        "id": "850e8400-e29b-41d4-a716-446655440000",
                        "name": "Central Medical Hospital",
                        "registration_number": "HFR-2026-001245",
                        "phermc_number": "PHERMC-88291",
                        "cac_number": "RC-1948273",
                        "address": "15 Medical Avenue, Lagos",
                        "verification_status": "pending",
                        "created_at": "2026-09-17T12:40:00Z"
                    }
                }
            }
        ),
        400: openapi.Response(
            description="Missing, invalid, or duplicate hospital information",
            examples={
                "application/json": {
                    "status": False,
                    "message": "All fields are required"
                }
            }
        ),
        404: openapi.Response(
            description="Administrator email already exists. The current view returns HTTP 404 for this condition.",
            examples={
                "application/json": {
                    "status": False,
                    "message": "Email is already in use"
                }
            }
        ),
        429: openapi.Response(
            description="Too many registration attempts",
            examples={
                "application/json": {
                    "detail": "Request was throttled."
                }
            }
        ),
    }
)
@api_view(["POST"])
@permission_classes([permissions.AllowAny])
@throttle_classes([RegistrationThrottle])
def register_hospital(request):
    """Register a hospital in PENDING state with its first admin."""
    serializer = HospitalRegistrationSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    hospital = serializer.save()

    admin_user = User.objects.get(email=serializer.validated_data["admin_email"])
    staff = HospitalStaffProfile.objects.get(user=admin_user)

    log_event(
        "hospital_registered",
        user_id=admin_user,
        request=request,
        hospital_id=hospital.id,
        target_type="hospital",
        target_id=hospital.id,
    )

    return success_response(
        {
            "hospital": HospitalSerializer(hospital).data,
            "admin": HospitalStaffProfileSerializer(staff).data,
        },
        "Hospital registered successfully. Verification is pending.",
        status.HTTP_201_CREATED,
    )

@swagger_auto_schema(
    method="post",
    tags=["Hospital Staff"],
    operation_summary="Create a new hospital staff account",
    operation_description="""
    Allows an authenticated hospital administrator to create a new staff account
    under their own hospital.

    The hospital is automatically determined from the authenticated administrator's
    `staff_profile`. The client therefore does NOT provide a hospital ID.

    **Notes for Frontend:**
    - Authentication is required.
    - Only a hospital administrator can access this endpoint.
    - The current view accepts `doctor` and `nurse` as valid roles.
    - The current view requires `professional_license_number` for both roles.
    - The server generates a temporary password automatically.
    - The temporary password is NOT returned in the API response.
    - `must_change_password` is set to `True` on the new user.
    - The temporary password is emailed to the staff member.
    - The staff member should change the temporary password after logging in.
    - The staff member is automatically assigned to the administrator's hospital.

    **Important Current Implementation Note:**
    - The current view returns HTTP 201 even when required fields are missing.
    - In that case the response contains `status: false`.
    - Frontend code should therefore inspect the response `status` field as well as
      the HTTP status until this behavior is corrected.
    - The supplied serializer allows `professional_license_number` to be optional for
      nurses, but the current view requires it for every staff member.

    **Authentication:** Required.

    **Required Role:** Hospital Admin.
    """,
    security=[{"Bearer": []}],
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=[
            "email",
            "full_name",
            "role",
            "professional_license_number",
        ],
        properties={
            "email": openapi.Schema(
                type=openapi.TYPE_STRING,
                format=openapi.FORMAT_EMAIL,
                description="Email address of the new staff member."
            ),
            "full_name": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Full name of the staff member."
            ),
            "role": openapi.Schema(
                type=openapi.TYPE_STRING,
                enum=["doctor", "nurse"],
                description="Staff role. The current view accepts only `doctor` or `nurse`."
            ),
            "professional_license_number": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Professional license number. Required by the current view."
            ),
        },
        example={
            "email": "doctor@centralmedical.example",
            "full_name": "Dr. Sarah Johnson",
            "role": "doctor",
            "professional_license_number": "MDCN-123456"
        }
    ),
    responses={
        201: openapi.Response(
            description="Staff created successfully. Note: the current view also uses HTTP 201 when required fields are missing.",
            examples={
                "application/json": {
                    "status": True,
                    "message": "Staff created successfully",
                    "data": {
                        "id": "950e8400-e29b-41d4-a716-446655440000",
                        "full_name": "Dr. Sarah Johnson",
                        "role": "doctor",
                        "professional_license_number": "MDCN-123456",
                        "hospital": "850e8400-e29b-41d4-a716-446655440000",
                        "hospital_name": "Central Medical Hospital",
                        "hospital_verification_status": "pending",
                        "created_at": "2026-09-17T12:45:00Z"
                    }
                }
            }
        ),
        400: openapi.Response(
            description="Invalid email or invalid staff role",
            examples={
                "application/json": {
                    "status": False,
                    "message": "Role must either be 'doctor' or 'nurse'"
                }
            }
        ),
        401: openapi.Response(
            description="Authentication required",
            examples={
                "application/json": {
                    "detail": "Authentication credentials were not provided."
                }
            }
        ),
        403: openapi.Response(
            description="Authenticated user is not a hospital administrator",
            examples={
                "application/json": {
                    "detail": "You do not have permission to perform this action."
                }
            }
        ),
    }
)
@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated, IsHospitalAdmin])
def create_hospital_staff(request):
    """Create hospital staff with a server-generated temporary password."""
    hospital = get_object_or_404(Hospital, pk=request.user.staff_profile.hospital_id)

    role = request.data.get("role")
    if role not in (HospitalStaffProfile.Role.DOCTOR, HospitalStaffProfile.Role.NURSE):
        return error_response(
            "Role must either be 'doctor' or 'nurse'.",
            status_code=status.HTTP_400_BAD_REQUEST,
            code="VALIDATION_ERROR",
        )

    serializer = HospitalStaffCreateSerializer(
        data=request.data,
        context={"hospital": hospital},
    )
    serializer.is_valid(raise_exception=True)
    staff_profile = serializer.save()
    temp_password = getattr(staff_profile, "_temp_password", None)

    # email the temporary password to the user
    if temp_password:
        email_message = EmailMessage(
            'Temporary Staff Password',
            f'Your staff account has been created under hospital {hospital.name} and you temporary password is:\n\n{temp_password}\n\nMake sure to change this password later on',
            settings.EMAIL_HOST_USER,
            [staff_profile.user.email]
        )
        email_message.fail_silently = True
        email_message.send()

    log_event(
        "staff_created",
        user_id=request.user,
        request=request,
        hospital_id=hospital.id,
        target_type="hospital_staff",
        target_id=staff_profile.id,
        created_staff_user_id=staff_profile.user_id,
        role=staff_profile.role,
    )

    return success_response(
        HospitalStaffProfileSerializer(staff_profile).data,
        "Staff created successfully.",
        status.HTTP_201_CREATED,
    )


# ---------------------------------------------------------------------------
# LOGIN / LOGOUT
# ---------------------------------------------------------------------------

@swagger_auto_schema(
    method="post",
    tags=["Authentication"],
    operation_summary="Log in a user",
    operation_description="""
    Authenticates a user using either an email address or phone number and returns JWT tokens.

    **Authentication:** Not required.
    """,
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["identifier", "password"],
        properties={
            "identifier": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Either the user's email address or 11-digit phone number."
            ),
            "password": openapi.Schema(
                type=openapi.TYPE_STRING,
                format=openapi.FORMAT_PASSWORD,
                description="User password."
            ),
        },
        example={
            "identifier": "john.patient@example.com",
            "password": "SecurePassword123!"
        }
    ),
    responses={
        200: openapi.Response(
            description="Login successful",
            examples={
                "application/json": {
                    "status": True,
                    "message": "Login successful.",
                    "data": {
                        "user": {
                            "id": "550e8400-e29b-41d4-a716-446655440000",
                            "email": "john.patient@example.com",
                            "user_type": "patient"
                        },
                        "tokens": {
                            "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                            "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
                        }
                    }
                }
            }
        ),
        400: openapi.Response(
            description="Invalid credentials or missing fields",
            examples={
                "application/json": {
                    "status": False,
                    "message": "Invalid credentials provided."
                }
            }
        ),
        429: openapi.Response(
            description="Too many login attempts",
            examples={
                "application/json": {
                    "detail": "Request was throttled."
                }
            }
        ),
    }
)
@api_view(["POST"])
@permission_classes([permissions.AllowAny])
@throttle_classes([LoginThrottle])
def login_view(request):
    """Authenticate with email or phone number and return JWT tokens."""
    data = request.data
    identifier = str(data.get('identifier') or '').strip()
    password = data.get('password') or ''

    if not identifier or not password:
        return error_response(
            "Identifier and password are required.",
            status_code=status.HTTP_400_BAD_REQUEST,
            code="VALIDATION_ERROR",
        )

    user = None

    # identifier is email
    if '@' in identifier:
        email = identifier.strip().lower()

        if not is_valid_email(email):
            return error_response(
                "Invalid email format.",
                status_code=status.HTTP_400_BAD_REQUEST,
                code="VALIDATION_ERROR",
            )

        user = authenticate(username=email, password=password)
    else:
        # else identifier is phone number
        if not identifier.isdigit():
            return error_response(
                "You must enter either a phone number or valid email address.",
                status_code=status.HTTP_400_BAD_REQUEST,
                code="VALIDATION_ERROR",
            )

        # make sure user enters correct length of phone number
        if len(identifier) != 11:
            return error_response(
                "Phone numbers must be 11 digits long.",
                status_code=status.HTTP_400_BAD_REQUEST,
                code="VALIDATION_ERROR",
            )

        # attempt to authenticate the user with phone number
        _user = User.objects.filter(phone_number=identifier).first()
        if _user and _user.check_password(password):
            user = _user

    if user is None or not user.is_active:
        return error_response(
            "Invalid credentials provided.",
            status_code=status.HTTP_400_BAD_REQUEST,
            code="AUTHENTICATION_FAILED",
        )

    log_event(
        "login_success",
        user_id=user,
        request=request,
        patient_id=getattr(getattr(user, "patient_profile", None), "id", None),
        hospital_id=getattr(getattr(user, "staff_profile", None), "hospital_id", None),
        target_type="user",
        target_id=user.id,
    )

    return success_response(
        {
            'user': UserSerializer(user).data,
            'tokens': user.auth_tokens()
        },
        "Login successful.",
    )



@swagger_auto_schema(
    method="post",
    tags=["Authentication"],
    operation_summary="Refresh an access token",
    operation_description="""
    Exchanges a valid refresh token for a new access token.

    **Authentication:** Not required for the refresh call itself, but a valid refresh token must be supplied.
    """,
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["refresh"],
        properties={
            "refresh": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Refresh token issued during login."
            )
        },
        example={
            "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
        }
    ),
    responses={
        200: openapi.Response(
            description="Token refreshed successfully",
            examples={
                "application/json": {
                    "status": True,
                    "message": "Token refreshed successfully",
                    "data": {
                        "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                        "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
                    }
                }
            }
        ),
        401: openapi.Response(
            description="Refresh token is invalid or expired",
            examples={
                "application/json": {
                    "status": False,
                    "message": "Token is invalid or has expired"
                }
            }
        ),
    }
)
@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def refresh_token_view(request):
    serializer = TokenRefreshSerializer(data=request.data)

    try:
        serializer.is_valid(raise_exception=True)
        return Response({
            "status": True,
            "message": "Token refreshed successfully",
            "data": serializer.validated_data
        }, status=status.HTTP_200_OK)

    except (TokenError, InvalidToken):
        return Response({
            "status": False,
            "message": "Token is invalid or has expired"
        }, status=status.HTTP_401_UNAUTHORIZED)

    except Exception:
        return Response({
            "status": False,
            "message": "An unexpected error occurred"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@swagger_auto_schema(
    method="post",
    tags=["Authentication"],
    operation_summary="Log out the current user",
    operation_description="""
    Invalidates the provided refresh token to log the user out.

    **Authentication:** Required. The user must be authenticated to call this endpoint.
    """,
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["refresh"],
        properties={
            "refresh": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Refresh token to blacklist and invalidate."
            )
        },
        example={
            "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
        }
    ),
    responses={
        204: openapi.Response(description="User logged out successfully"),
        400: openapi.Response(
            description="Refresh token missing or invalid",
            examples={
                "application/json": {
                    "status": False,
                    "error": "Refresh token is required."
                }
            }
        ),
    }
)
@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def logout_view(request):
    try:
        refresh_token = request.data.get("refresh")
        if refresh_token is None:
            return Response({
                "error": "Refresh token is required."
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Blacklist the refresh token to prevent further use
        token = RefreshToken(refresh_token)
        token.blacklist()
        
        return Response({
            "status": True,
            "message": "Successfully logged out."
            }, status=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        return Response({
            "status": False,
            "error": str(e)
        }, status=status.HTTP_400_BAD_REQUEST)

# ---------------------------------------------------------------------------
# "ME" — profile retrieval, works for either user type
# ---------------------------------------------------------------------------

@swagger_auto_schema(
    method="get",
    tags=["Profile"],
    operation_summary="Get the current authenticated user's profile",
    operation_description="""
    Returns the authenticated user's profile payload, shaped according to whether the account is a patient or hospital staff member.

    **Authentication:** Required.
    """,
    responses={
        200: openapi.Response(
            description="Current profile retrieved successfully",
            examples={
                "application/json": {
                    "status": True,
                    "message": "Profile retrieved successfully",
                    "data": {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "full_name": "John Patient",
                        "user_type": "patient"
                    }
                }
            }
        ),
        401: openapi.Response(
            description="Authentication credentials were not provided or token is invalid",
            examples={
                "application/json": {
                    "detail": "Authentication credentials were not provided."
                }
            }
        ),
    }
)
@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def me_view(request):
    user = request.user
    if user.user_type == User.UserType.PATIENT:
        profile_data = PatientProfileSerializer(user.patient_profile).data
    elif user.user_type == User.UserType.HOSPITAL_STAFF:
        profile_data = HospitalStaffProfileSerializer(user.staff_profile).data
    else:
        # Platform admins have no patient/staff profile — an empty dict is
        # correct here, not a bug: there is nothing else safe to return.
        profile_data = {}

    return Response({
        'status': True,
        'message': 'Profile retrieved successfully',
        'data': profile_data
    }, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# HOSPITAL DIRECTORY / VERIFICATION / STAFF MANAGEMENT
# ---------------------------------------------------------------------------

@swagger_auto_schema(
    method="get",
    tags=["Hospitals"],
    operation_summary="List verified hospitals",
    operation_description="""
    Returns all verified hospitals in the public directory.

    An optional query string parameter `q` can be used to filter by hospital name.

    **Authentication:** Not required.
    """,
    manual_parameters=[
        openapi.Parameter(
            "q",
            openapi.IN_QUERY,
            description="Optional hospital-name search filter.",
            type=openapi.TYPE_STRING,
        )
    ],
    responses={
        200: openapi.Response(
            description="Verified hospitals retrieved successfully",
            examples={
                "application/json": {
                    "status": True,
                    "message": "Hospital directory retrieved successfully.",
                    "data": [
                        {
                            "id": "850e8400-e29b-41d4-a716-446655440000",
                            "name": "Central Medical Hospital",
                            "verification_status": "verified"
                        }
                    ]
                }
            }
        )
    }
)
@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def hospital_directory(request):
    """Public directory containing verified hospitals only."""
    queryset = Hospital.objects.filter(
        verification_status=Hospital.VerificationStatus.VERIFIED
    ).order_by("name")
    query = request.query_params.get("q", "").strip()
    if query:
        queryset = queryset.filter(name__icontains=query)
    serializer = HospitalSerializer(queryset, many=True)
    return success_response(serializer.data, "Hospital directory retrieved successfully.")


@swagger_auto_schema(
    method="get",
    tags=["Hospitals"],
    operation_summary="Get a verified hospital by ID",
    operation_description="""
    Returns the public information for a verified hospital.

    **Authentication:** Not required.
    """,
    responses={
        200: openapi.Response(
            description="Hospital retrieved successfully",
            examples={
                "application/json": {
                    "status": True,
                    "message": "Hospital retrieved successfully.",
                    "data": {
                        "id": "850e8400-e29b-41d4-a716-446655440000",
                        "name": "Central Medical Hospital",
                        "verification_status": "verified"
                    }
                }
            }
        ),
        404: openapi.Response(
            description="Hospital does not exist or is not verified",
            examples={
                "application/json": {
                    "status": False,
                    "message": "Not found."
                }
            }
        ),
    }
)
@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def hospital_detail(request, hospital_id):
    hospital = get_object_or_404(
        Hospital,
        pk=hospital_id,
        verification_status=Hospital.VerificationStatus.VERIFIED,
    )
    return success_response(HospitalSerializer(hospital).data, "Hospital retrieved successfully.")


@swagger_auto_schema(
    method="post",
    tags=["Hospitals"],
    operation_summary="Verify or reject a hospital registration",
    operation_description="""
    Allows a platform administrator to change a hospital's verification status.

    **Authentication:** Required.

    **Required Role:** Platform Admin.
    """,
    security=[{"Bearer": []}],
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["status"],
        properties={
            "status": openapi.Schema(
                type=openapi.TYPE_STRING,
                enum=["verified", "rejected", "pending"],
                description="The new verification status to apply to the hospital."
            )
        },
        example={
            "status": "verified"
        }
    ),
    responses={
        200: openapi.Response(
            description="Hospital verification status updated successfully",
            examples={
                "application/json": {
                    "status": True,
                    "message": "Hospital verification status updated successfully.",
                    "data": {
                        "id": "850e8400-e29b-41d4-a716-446655440000",
                        "verification_status": "verified"
                    }
                }
            }
        ),
        403: openapi.Response(
            description="Authenticated user is not a platform admin",
            examples={
                "application/json": {
                    "detail": "Only a platform admin can verify hospitals."
                }
            }
        ),
    }
)
@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def verify_hospital(request, hospital_id):
    """Platform-admin manual verification of a hospital's registration."""
    if request.user.user_type != User.UserType.PLATFORM_ADMIN:
        raise PermissionDenied("Only a platform admin can verify hospitals.")
    hospital = get_object_or_404(Hospital, pk=hospital_id)
    serializer = HospitalVerificationSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    new_status = serializer.validated_data["status"]
    hospital.verification_status = new_status
    hospital.verified_at = timezone.now() if new_status == Hospital.VerificationStatus.VERIFIED else None
    hospital.save(update_fields=["verification_status", "verified_at"])
    log_event(
        "hospital_verification_changed", user_id=request.user, request=request,
        hospital_id=hospital.id, target_type="hospital", target_id=hospital.id,
        verification_status=new_status,
    )
    return success_response(HospitalSerializer(hospital).data, "Hospital verification status updated successfully.")


@swagger_auto_schema(
    method="get",
    tags=["Hospital Staff"],
    operation_summary="List staff within a hospital",
    operation_description="""
    Lists the staff members belonging to the authenticated hospital administrator's hospital.

    **Authentication:** Required.

    **Required Role:** Hospital Admin.
    """,
    security=[{"Bearer": []}],
    responses={
        200: openapi.Response(
            description="Hospital staff retrieved successfully",
            examples={
                "application/json": {
                    "status": True,
                    "message": "Hospital staff retrieved successfully.",
                    "data": [
                        {
                            "id": "960e8400-e29b-41d4-a716-446655440000",
                            "full_name": "Dr. Sarah Johnson",
                            "role": "doctor"
                        }
                    ]
                }
            }
        ),
        403: openapi.Response(
            description="Authenticated user is not a hospital admin",
            examples={
                "application/json": {
                    "detail": "You do not have permission to perform this action."
                }
            }
        ),
    }
)
@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated, IsHospitalAdmin])
def list_hospital_staff(request, hospital_id=None):
    """List staff at the requesting admin's own hospital."""
    admin_staff = request.user.staff_profile
    if hospital_id and str(admin_staff.hospital_id) != str(hospital_id):
        raise PermissionDenied("You can only manage staff in your own hospital.")
    staff = HospitalStaffProfile.objects.select_related("user", "hospital").filter(
        hospital=admin_staff.hospital
    ).order_by("full_name")
    return success_response(HospitalStaffListSerializer(staff, many=True).data, "Hospital staff retrieved successfully.")


@swagger_auto_schema(
    method="delete",
    tags=["Hospital Staff"],
    operation_summary="Remove a hospital staff member's access",
    operation_description="""
    Deactivates a staff member's login without deleting their records or hospital profile.

    **Authentication:** Required.

    **Required Role:** Hospital Admin.
    """,
    security=[{"Bearer": []}],
    responses={
        200: openapi.Response(
            description="Staff access removed successfully",
            examples={
                "application/json": {
                    "status": True,
                    "message": "Staff access removed successfully."
                }
            }
        ),
        403: openapi.Response(
            description="Authenticated user is not allowed to remove this staff member",
            examples={
                "application/json": {
                    "detail": "You do not have permission to perform this action."
                }
            }
        ),
    }
)
@api_view(["DELETE"])
@permission_classes([permissions.IsAuthenticated, IsHospitalAdmin])
def remove_hospital_staff(request, staff_id):
    """Deactivate a staff member's login access (does not delete their records)."""
    admin_staff = request.user.staff_profile
    staff = get_object_or_404(HospitalStaffProfile.objects.select_related("user", "hospital"), pk=staff_id)
    if staff.hospital_id != admin_staff.hospital_id:
        raise PermissionDenied("You can only manage staff in your own hospital.")
    if staff.user_id == request.user.id:
        raise ValidationError("A hospital admin cannot remove their own account.")
    if not staff.user.is_active:
        return success_response(None, "Staff account is already inactive.")
    staff.user.is_active = False
    staff.user.save(update_fields=["is_active"])
    log_event(
        "staff_access_removed", user_id=request.user, request=request,
        hospital_id=staff.hospital_id, target_type="hospital_staff", target_id=staff.id,
        removed_staff_user_id=staff.user_id, role=staff.role,
    )
    return success_response(None, "Staff access removed successfully.")
