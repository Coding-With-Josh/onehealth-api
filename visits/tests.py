from datetime import date

from django.core.exceptions import ValidationError
from django.test import TestCase

from users.models import Hospital, HospitalStaffProfile, PatientProfile, User

from .models import Medication, Vital, Visit


class VisitVitalMedicationTests(TestCase):
    def setUp(self):
        self.patient_user = User.objects.create_user(email="patient@example.com", password="password123", user_type=User.UserType.PATIENT)
        self.patient = PatientProfile.objects.create(
            user=self.patient_user, full_name="Test Patient", date_of_birth=date(1990, 1, 1), account_type=PatientProfile.AccountType.SELF_MANAGED
        )
        self.hospital = Hospital.objects.create(name="Test Hospital", registration_number="HOSP-001", verification_status=Hospital.VerificationStatus.VERIFIED)
        self.staff_user = User.objects.create_user(email="doctor@example.com", password="password123", user_type=User.UserType.HOSPITAL_STAFF)
        self.staff = HospitalStaffProfile.objects.create(user=self.staff_user, hospital=self.hospital, full_name="Dr Test", role=HospitalStaffProfile.Role.DOCTOR, professional_license_number="LIC-1")
        self.visit = Visit.objects.create(patient=self.patient, hospital=self.hospital, created_by_staff=self.staff)

    def test_visit_belongs_to_staff_hospital(self):
        other = Hospital.objects.create(name="Other", registration_number="HOSP-002")
        with self.assertRaises(ValidationError):
            Visit.objects.create(patient=self.patient, hospital=other, created_by_staff=self.staff)

    def test_vitals_are_append_only(self):
        vital = Vital.objects.create(visit=self.visit, recorded_by_staff=self.staff, heart_rate=70)
        vital.heart_rate = 80
        with self.assertRaises(ValidationError):
            vital.save()
        with self.assertRaises(ValidationError):
            vital.delete()

    def test_medication_shape(self):
        medication = Medication.objects.create(
            patient=self.patient, visit=self.visit, medication="Amoxicillin", dose="500 mg", route="oral", frequency="3 times daily", duration="7 days", reason="Infection", status=Medication.Status.CURRENT, prescribed_by_staff=self.staff,
        )
        self.assertEqual(medication.medication, "Amoxicillin")
