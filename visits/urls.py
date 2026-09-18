from django.urls import path

from . import views

urlpatterns = [
    path("visits/", views.start_visit, name="start-visit"),
    path("visits/<uuid:visit_id>/checkout/", views.checkout_visit, name="checkout-visit"),
    path("patients/me/visits/", views.my_visits, name="my-visits"),
    path("visits/<uuid:visit_id>/request-checkout/", views.request_checkout, name="request-checkout"),
    path("visits/<uuid:visit_id>/records/", views.visit_records, name="visit-records"),
    path("visits/<uuid:visit_id>/vitals/", views.visit_vitals, name="visit-vitals"),
    path("visits/<uuid:visit_id>/medications/", views.visit_medications, name="visit-medications"),
    path("patients/me/medications/", views.my_medications, name="my-medications"),
]
