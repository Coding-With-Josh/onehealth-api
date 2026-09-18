from django.urls import path

from . import views

# Mount this in your project's root urls.py, e.g.:
#   path("api/v1/auth/", include("users.urls"))

urlpatterns = [
    # --- Registration ---
    path("register/patient/", views.register_patient, name="register-patient"),
    path("register/hospital/", views.register_hospital, name="register-hospital"),

    # --- Dependents (nested under patient, but kept here for auth-app cohesion) ---
    path("patients/me/dependents/", views.register_dependent, name="register-dependent"),

    # --- Hospital staff management ---
    path("hospitals/me/staff/", views.create_hospital_staff, name="hospital-staff-create"),
    path("hospitals/<uuid:hospital_id>/staff/", views.list_hospital_staff, name="hospital-staff-list"),
    path("staff/<uuid:staff_id>/", views.remove_hospital_staff, name="hospital-staff-remove"),

    # --- Hospital directory / verification ---
    path("hospitals/", views.hospital_directory, name="hospital-directory"),
    path("hospitals/<uuid:hospital_id>/", views.hospital_detail, name="hospital-detail"),
    path("hospitals/<uuid:hospital_id>/verify/", views.verify_hospital, name="hospital-verify"),

    # --- Login / token lifecycle ---
    path("login/", views.login_view, name="login"),
    path("login/refresh/", views.refresh_token_view, name="login-refresh"),
    path("logout/", views.logout_view, name="logout"),

    # --- Profile ---
    path("me/", views.me_view, name="me"),

]
