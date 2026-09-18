from django.apps import AppConfig


class UsersConfig(AppConfig):
    """
    Config for the 'users' app.

    This app owns ALL authentication + identity for OneHealth:
    - CustomUser (the actual login-capable account)
    - Hospital (an organization, not a user)
    - PatientProfile (a patient OR a dependent with no login of their own)
    - HospitalStaffProfile (a staff member belonging to a hospital)

    Everything else in the platform (records, visits, access requests, etc.)
    should live in OTHER apps and just reference these models by FK —
    keep auth/identity isolated from business logic.
    """
    default_auto_field = "django.db.models.BigAutoField"
    name = "users"
