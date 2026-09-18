from django.urls import path

from . import views

urlpatterns = [
    path("patients/me/records/", views.my_records, name="my-medical-records"),
    path("records/<uuid:record_id>/verify/", views.verify_record, name="verify-medical-record"),
    path("records/<uuid:record_id>/supersede/", views.supersede_record, name="supersede-medical-record"),
]
