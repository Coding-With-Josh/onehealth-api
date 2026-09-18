from django.core.exceptions import ValidationError
from django.db import models
import uuid
from django.utils import timezone

from users.models import Hospital, HospitalStaffProfile, PatientProfile


class MedicalRecord(models.Model):
    class VerificationStatus(models.TextChoices):
        SELF_REPORTED = "self_reported", "Self-reported"
        DOCTOR_VERIFIED = "doctor_verified", "Doctor-verified"

    id = models.UUIDField(primary_key=True, editable=False, default=uuid.uuid4)
    patient = models.ForeignKey(
        PatientProfile,
        on_delete=models.PROTECT,
        related_name="medical_records",
    )
    entry_type = models.CharField(max_length=100)
    description = models.TextField()
    verification_status = models.CharField(
        max_length=30,
        choices=VerificationStatus.choices,
        default=VerificationStatus.SELF_REPORTED,
    )
    verified_by_staff = models.ForeignKey(
        HospitalStaffProfile,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="verified_medical_records",
    )
    created_by_staff = models.ForeignKey(
        HospitalStaffProfile,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="created_medical_records",
    )
    visit = models.ForeignKey(
        "visits.Visit",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="medical_records",
    )
    hospital = models.ForeignKey(
        Hospital,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="medical_records",
    )
    supersedes_entry = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="superseding_entries",
    )
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        db_table = "medical_records"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["patient", "created_at"]),
            models.Index(fields=["patient", "entry_type"]),
            models.Index(fields=["verification_status"]),
        ]

    def clean(self):
        errors = {}
        if self.visit_id and self.visit.patient_id != self.patient_id:
            errors["visit"] = "Visit must belong to the same patient."
        if self.visit_id and self.visit.status == "checked_out" and self.created_by_staff_id:
            errors["visit"] = "Clinical records cannot be added to a checked-out visit."
        if self.visit_id and self.hospital_id and self.visit.hospital_id != self.hospital_id:
            errors["hospital"] = "Hospital must match the visit hospital."
        if self.visit_id and self.created_by_staff_id and self.visit.hospital_id != self.created_by_staff.hospital_id:
            errors["created_by_staff"] = "Creating staff must belong to the visit hospital."
        if self.supersedes_entry_id:
            if self.supersedes_entry_id == self.pk:
                errors["supersedes_entry"] = "A record cannot supersede itself."
            elif self.supersedes_entry and self.supersedes_entry.patient_id != self.patient_id:
                errors["supersedes_entry"] = "A record can only supersede an entry belonging to the same patient."

        if self.verification_status == self.VerificationStatus.DOCTOR_VERIFIED and not self.verified_by_staff_id:
            errors["verified_by_staff"] = "Doctor-verified records must identify the verifying staff member."

        if self.verified_by_staff and self.verified_by_staff.role != HospitalStaffProfile.Role.DOCTOR:
            errors["verified_by_staff"] = "Only a doctor can verify a medical record."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Medical records are append-only and cannot be edited.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Medical records are append-only and cannot be deleted.")

    def __str__(self):
        return f"{self.entry_type} — {self.patient.full_name}"
