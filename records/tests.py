import uuid
from datetime import date

from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from users.models import Hospital, HospitalStaffProfile, PatientProfile, User
from .models import MedicalRecord
from .views import my_records


class MedicalRecordModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="patient@example.com",
            password="StrongPassword123!",
            user_type=User.UserType.PATIENT,
        )
        self.patient = PatientProfile.objects.create(
            user=self.user,
            full_name="Test Patient",
            date_of_birth=date(1990, 1, 1),
            account_type=PatientProfile.AccountType.SELF_MANAGED,
        )

    def test_default_status_is_self_reported(self):
        record = MedicalRecord.objects.create(
            patient=self.patient,
            entry_type="allergy",
            description="Penicillin",
        )
        self.assertEqual(record.verification_status, MedicalRecord.VerificationStatus.SELF_REPORTED)

    def test_existing_record_cannot_be_edited(self):
        record = MedicalRecord.objects.create(
            patient=self.patient, entry_type="condition", description="Asthma"
        )
        record.description = "Updated"
        with self.assertRaises(ValidationError):
            record.save()

    def test_existing_record_cannot_be_deleted(self):
        record = MedicalRecord.objects.create(
            patient=self.patient, entry_type="condition", description="Asthma"
        )
        with self.assertRaises(ValidationError):
            record.delete()

    def test_correction_must_belong_to_same_patient(self):
        other_user = User.objects.create_user(
            email="other@example.com",
            password="StrongPassword123!",
            user_type=User.UserType.PATIENT,
        )
        other = PatientProfile.objects.create(
            user=other_user,
            full_name="Other Patient",
            date_of_birth=date(1990, 1, 1),
            account_type=PatientProfile.AccountType.SELF_MANAGED,
        )
        original = MedicalRecord.objects.create(
            patient=other, entry_type="condition", description="Asthma"
        )
        correction = MedicalRecord(
            patient=self.patient,
            entry_type="condition",
            description="No asthma",
            supersedes_entry=original,
        )
        with self.assertRaises(ValidationError):
            correction.full_clean()


class MyRecordsAPITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="patient@example.com",
            password="StrongPassword123!",
            user_type=User.UserType.PATIENT,
        )
        self.patient = PatientProfile.objects.create(
            user=self.user,
            full_name="Test Patient",
            date_of_birth=date(1990, 1, 1),
            account_type=PatientProfile.AccountType.SELF_MANAGED,
        )
        self.factory = APIRequestFactory()

    def test_patient_can_add_self_reported_record(self):
        request = self.factory.post(
            "/api/v1/patients/me/records/",
            {"entry_type": "allergy", "description": "Penicillin"},
            format="json",
        )
        force_authenticate(request, user=self.user)
        response = my_records(request)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(MedicalRecord.objects.count(), 1)
        self.assertEqual(MedicalRecord.objects.first().patient, self.patient)

    def test_patient_can_list_own_records(self):
        MedicalRecord.objects.create(
            patient=self.patient, entry_type="condition", description="Asthma"
        )
        request = self.factory.get("/api/v1/patients/me/records/")
        force_authenticate(request, user=self.user)
        response = my_records(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["data"]), 1)

class SupersedeRecordAPITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="patient@example.com",
            password="StrongPassword123!",
            user_type=User.UserType.PATIENT,
        )
        self.patient = PatientProfile.objects.create(
            user=self.user,
            full_name="Test Patient",
            date_of_birth=date(1990, 1, 1),
            account_type=PatientProfile.AccountType.SELF_MANAGED,
        )
        self.original = MedicalRecord.objects.create(
            patient=self.patient,
            entry_type="allergy",
            description="Penicillin",
        )
        self.factory = APIRequestFactory()

    def test_patient_can_supersede_own_record(self):
        from .views import supersede_record
        request = self.factory.post(
            f"/api/v1/records/{self.original.id}/supersede/",
            {"description": "Penicillin allergy — patient correction"},
            format="json",
        )
        force_authenticate(request, user=self.user)
        response = supersede_record(request, self.original.id)
        self.assertEqual(response.status_code, 201)
        replacement = MedicalRecord.objects.exclude(pk=self.original.id).get()
        self.assertEqual(replacement.supersedes_entry_id, self.original.id)
