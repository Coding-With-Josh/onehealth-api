from datetime import date

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from users.models import PatientProfile, User
from .models import PatientCard


class PatientCardTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="patient@example.com", password="StrongPassword123!", user_type=User.UserType.PATIENT
        )
        self.patient = PatientProfile.objects.create(
            user=self.user, full_name="Test Patient", date_of_birth=date(1990, 1, 1),
            account_type=PatientProfile.AccountType.SELF_MANAGED,
        )

    def test_card_generates_reference_and_expiry(self):
        card = PatientCard.objects.create(patient=self.patient)
        self.assertTrue(card.card_reference.startswith("OH-"))
        self.assertGreater(card.expires_at, timezone.now())

    def test_card_cannot_be_directly_edited(self):
        card = PatientCard.objects.create(patient=self.patient)
        card.status = PatientCard.Status.REVOKED
        with self.assertRaises(ValidationError):
            card.save()

    def test_revoke_then_renew_is_blocked(self):
        card = PatientCard.objects.create(patient=self.patient)
        card.revoke()
        with self.assertRaises(ValidationError):
            card.renew()
