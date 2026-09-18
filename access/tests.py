from datetime import date

from django.test import TestCase

from users.models import PatientProfile, User
from .models import EmergencyContact


class EmergencyContactTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="patient@example.com", password="StrongPassword123!", user_type=User.UserType.PATIENT
        )
        self.patient = PatientProfile.objects.create(
            user=self.user, full_name="Test Patient", date_of_birth=date(1990, 1, 1),
            account_type=PatientProfile.AccountType.SELF_MANAGED,
        )

    def test_contact_gets_secure_response_token(self):
        contact = EmergencyContact.objects.create(
            patient=self.patient, full_name="Jane Contact", phone_number="08000000000", priority_order=1
        )
        self.assertTrue(contact.response_token)
        self.assertGreaterEqual(len(contact.response_token), 32)
