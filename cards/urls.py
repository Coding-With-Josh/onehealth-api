from django.urls import path

from . import views

urlpatterns = [
    path("patients/me/card/", views.card, name="patient-card"),
    path("patients/me/card/renew/", views.renew_card, name="renew-card"),
    path("patients/me/card/revoke/", views.revoke_card, name="revoke-card"),
    path("cards/lookup/", views.lookup_card, name="card-lookup"),
]
