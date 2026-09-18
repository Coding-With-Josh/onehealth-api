"""
python manage.py seed_demo

Creates a complete, runnable demo dataset:

  Platform admin
    email: admin@onehealth.ng  /  password: Admin1234!

  Hospital (auto-verified — matches seed registry)
    Name: Central Medical Hospital Lagos
    Reg#: NHFR-LG-002
    Admin email: admin@centralmedical.ng  /  password: Hospital1234!
    Doctor email: doctor@centralmedical.ng  /  password: Doctor1234!
    Nurse email:  nurse@centralmedical.ng   /  password: Nurse1234!

  Patient (self-managed, active card issued)
    email: nosa@example.com  /  password: Patient1234!
    Phone: 08012345678
    Profile: Nosa Adekunle, DOB 1990-05-15, male, O+
    Emergency contact: Amaka Adekunle (wife)
    Medical records: 2 self-reported entries

Run this once against a fresh database. Re-running is safe — it skips
objects that already exist.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from users.models import Hospital, HospitalStaffProfile, PatientProfile, User
from users.seed_hospitals import verify_against_registry
from cards.models import PatientCard
from access.models import EmergencyContact
from records.models import MedicalRecord


class Command(BaseCommand):
    help = "Seed demo data for hackathon presentation"

    def handle(self, *args, **options):
        self.stdout.write("Seeding demo data…")

        # ── Platform admin ────────────────────────────────────────────────
        admin, created = User.objects.get_or_create(
            email="admin@onehealth.ng",
            defaults={"user_type": User.UserType.PLATFORM_ADMIN, "is_staff": True, "is_superuser": True},
        )
        if created:
            admin.set_password("Admin1234!")
            admin.save()
            self.stdout.write("  ✓ Platform admin created")
        else:
            self.stdout.write("  · Platform admin already exists")

        # ── Verified hospital ─────────────────────────────────────────────
        hospital, h_created = Hospital.objects.get_or_create(
            registration_number="NHFR-LG-002",
            defaults={
                "name": "Central Medical Hospital Lagos",
                "address": "23 Marina Street, Lagos Island, Lagos",
                "phermc_number": "PHERMC-LG-002",
                "cac_number": "CAC-LG-002",
                "verification_status": Hospital.VerificationStatus.VERIFIED,
                "verified_at": timezone.now(),
            },
        )
        if h_created:
            self.stdout.write("  ✓ Hospital created + verified")
        else:
            self.stdout.write("  · Hospital already exists")

        # Hospital admin
        h_admin_user, created = User.objects.get_or_create(
            email="admin@centralmedical.ng",
            defaults={"user_type": User.UserType.HOSPITAL_STAFF},
        )
        if created:
            h_admin_user.set_password("Hospital1234!")
            h_admin_user.save()
            HospitalStaffProfile.objects.create(
                user=h_admin_user, hospital=hospital,
                full_name="Dr. Chidi Okonkwo", role=HospitalStaffProfile.Role.ADMIN,
            )
            self.stdout.write("  ✓ Hospital admin created")

        # Doctor
        doctor_user, created = User.objects.get_or_create(
            email="doctor@centralmedical.ng",
            defaults={"user_type": User.UserType.HOSPITAL_STAFF},
        )
        if created:
            doctor_user.set_password("Doctor1234!")
            doctor_user.save()
            HospitalStaffProfile.objects.create(
                user=doctor_user, hospital=hospital,
                full_name="Dr. Ngozi Eze", role=HospitalStaffProfile.Role.DOCTOR,
                professional_license_number="MDCN-12345",
            )
            self.stdout.write("  ✓ Doctor created")

        # Nurse
        nurse_user, created = User.objects.get_or_create(
            email="nurse@centralmedical.ng",
            defaults={"user_type": User.UserType.HOSPITAL_STAFF},
        )
        if created:
            nurse_user.set_password("Nurse1234!")
            nurse_user.save()
            HospitalStaffProfile.objects.create(
                user=nurse_user, hospital=hospital,
                full_name="Nurse Taiwo Adebayo", role=HospitalStaffProfile.Role.NURSE,
            )
            self.stdout.write("  ✓ Nurse created")

        # ── Patient ───────────────────────────────────────────────────────
        patient_user, created = User.objects.get_or_create(
            email="nosa@example.com",
            defaults={
                "user_type": User.UserType.PATIENT,
                "phone_number": "08012345678",
            },
        )
        if created:
            patient_user.set_password("Patient1234!")
            patient_user.save()

        patient_profile, p_created = PatientProfile.objects.get_or_create(
            user=patient_user,
            defaults={
                "full_name": "Nosa Adekunle",
                "date_of_birth": "1990-05-15",
                "gender": "male",
                "blood_type": "O+",
                "account_type": PatientProfile.AccountType.SELF_MANAGED,
            },
        )
        if created:
            self.stdout.write("  ✓ Patient created")
        else:
            self.stdout.write("  · Patient already exists")

        # Emergency contact
        EmergencyContact.objects.get_or_create(
            patient=patient_profile,
            phone_number="08098765432",
            defaults={
                "full_name": "Amaka Adekunle",
                "relationship": "Wife",
                "email": "amaka@example.com",
                "priority_order": 1,
            },
        )

        # Medical records
        if not MedicalRecord.objects.filter(patient=patient_profile).exists():
            MedicalRecord.objects.create(
                patient=patient_profile,
                entry_type="allergy",
                description="Penicillin — causes severe rash and throat swelling.",
                verification_status=MedicalRecord.VerificationStatus.SELF_REPORTED,
            )
            MedicalRecord.objects.create(
                patient=patient_profile,
                entry_type="condition",
                description="Type 2 Diabetes — diagnosed 2018. Currently managed with Metformin 500mg twice daily.",
                verification_status=MedicalRecord.VerificationStatus.SELF_REPORTED,
            )
            MedicalRecord.objects.create(
                patient=patient_profile,
                entry_type="medication",
                description="Metformin 500mg — twice daily with meals. Started January 2019.",
                verification_status=MedicalRecord.VerificationStatus.SELF_REPORTED,
            )
            self.stdout.write("  ✓ Patient medical records created")

        # Active patient card
        if not PatientCard.objects.filter(patient=patient_profile, status=PatientCard.Status.ACTIVE).exists():
            PatientCard.objects.create(patient=patient_profile)
            self.stdout.write("  ✓ Patient card issued")

        self.stdout.write(self.style.SUCCESS("\nDemo data ready.\n"))
        self.stdout.write("  Platform admin:   admin@onehealth.ng        / Admin1234!")
        self.stdout.write("  Hospital admin:   admin@centralmedical.ng   / Hospital1234!")
        self.stdout.write("  Doctor:           doctor@centralmedical.ng  / Doctor1234!")
        self.stdout.write("  Nurse:            nurse@centralmedical.ng   / Nurse1234!")
        self.stdout.write("  Patient:          nosa@example.com          / Patient1234!")
        self.stdout.write("  Patient phone:    08012345678")
