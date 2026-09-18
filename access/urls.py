from django.urls import path

from . import views

urlpatterns = [
    path("access-requests/", views.create_access_request, name="create-access-request"),
    path("patients/me/access-requests/", views.my_access_requests, name="my-access-requests"),
    path("access-requests/<uuid:request_id>/approve/", views.approve_access_request, name="approve-access-request"),
    path("access-requests/<uuid:request_id>/deny/", views.deny_access_request, name="deny-access-request"),
    path("access-grants/active/", views.active_grants, name="active-access-grants"),
    path("access-grants/<uuid:grant_id>/revoke/", views.revoke_grant, name="revoke-access-grant"),
    path("access-grants/hospital/active/", views.hospital_active_grants, name="hospital-active-access-grants"),
    path("patients/<uuid:patient_id>/", views.hospital_patient_profile, name="hospital-patient-profile"),
    path("patients/<uuid:patient_id>/records/", views.hospital_patient_records, name="hospital-patient-records"),
    path("patients/me/emergency-contacts/", views.emergency_contacts, name="emergency-contacts"),
    path("emergency-contacts/<uuid:contact_id>/", views.delete_emergency_contact, name="delete-emergency-contact"),
    path("emergency-contacts/<uuid:contact_id>/respond/", views.emergency_contact_respond, name="emergency-contact-respond"),
    path("escalations/<uuid:escalation_id>/", views.escalation_detail, name="escalation-detail"),
]
