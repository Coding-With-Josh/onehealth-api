import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from users.models import Hospital, HospitalStaffProfile, PatientProfile


class Visit(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        CHECKED_OUT = "checked_out", "Checked out"
        ESCALATED = "escalated", "Escalated"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(PatientProfile, on_delete=models.PROTECT, related_name="visits")
    hospital = models.ForeignKey(Hospital, on_delete=models.PROTECT, related_name="visits")
    admitted_at = models.DateTimeField(default=timezone.now)
    checked_out_at = models.DateTimeField(null=True, blank=True)
    checkout_requested_by_patient_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    created_by_staff = models.ForeignKey(
        HospitalStaffProfile,
        on_delete=models.PROTECT,
        related_name="created_visits",
    )

    class Meta:
        db_table = "visits"
        ordering = ["-admitted_at"]
        indexes = [
            models.Index(fields=["patient", "admitted_at"]),
            models.Index(fields=["hospital", "status"]),
        ]

    def clean(self):
        if self.created_by_staff_id and self.hospital_id != self.created_by_staff.hospital_id:
            raise ValidationError({"created_by_staff": "Visit staff must belong to the visit hospital."})
        if self.status == self.Status.ACTIVE and self.checked_out_at:
            raise ValidationError({"checked_out_at": "An active visit cannot have a checkout time."})
        if self.status == self.Status.CHECKED_OUT and not self.checked_out_at:
            raise ValidationError({"checked_out_at": "A checked-out visit must have a checkout time."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"Visit {self.id} — {self.patient.full_name} at {self.hospital.name}"


class Vital(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    visit = models.ForeignKey(Visit, on_delete=models.PROTECT, related_name="vitals")
    recorded_by_staff = models.ForeignKey(
        HospitalStaffProfile,
        on_delete=models.PROTECT,
        related_name="recorded_vitals",
    )
    recorded_at = models.DateTimeField(default=timezone.now, editable=False)

    blood_pressure_systolic = models.PositiveSmallIntegerField(null=True, blank=True)
    blood_pressure_diastolic = models.PositiveSmallIntegerField(null=True, blank=True)
    heart_rate = models.PositiveSmallIntegerField(null=True, blank=True)
    temperature_c = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    respiratory_rate = models.PositiveSmallIntegerField(null=True, blank=True)
    oxygen_saturation = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    weight_kg = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    height_cm = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "vitals"
        ordering = ["-recorded_at"]
        indexes = [models.Index(fields=["visit", "recorded_at"])]

    def clean(self):
        errors = {}
        if self.recorded_by_staff_id and self.visit_id and self.recorded_by_staff.hospital_id != self.visit.hospital_id:
            errors["recorded_by_staff"] = "Staff member must belong to the visit hospital."
        if self.visit_id and self.visit.status == Visit.Status.CHECKED_OUT:
            errors["visit"] = "Vitals cannot be added to a checked-out visit."
        if self.blood_pressure_systolic is None and self.blood_pressure_diastolic is not None:
            errors["blood_pressure_systolic"] = "Systolic pressure is required when diastolic pressure is provided."
        if self.blood_pressure_diastolic is None and self.blood_pressure_systolic is not None:
            errors["blood_pressure_diastolic"] = "Diastolic pressure is required when systolic pressure is provided."
        if self.oxygen_saturation is not None and not Decimal("0") <= self.oxygen_saturation <= Decimal("100"):
            errors["oxygen_saturation"] = "Oxygen saturation must be between 0 and 100."
        if self.temperature_c is not None and not Decimal("20") <= self.temperature_c <= Decimal("50"):
            errors["temperature_c"] = "Temperature must be between 20 and 50 °C."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Vitals are append-only and cannot be edited.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Vitals are append-only and cannot be deleted.")

    def __str__(self):
        return f"Vitals — {self.visit.patient.full_name} — {self.recorded_at:%Y-%m-%d %H:%M}"


class Medication(models.Model):
    class Status(models.TextChoices):
        CURRENT = "current", "Current"
        PREVIOUS = "previous", "Previous"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(PatientProfile, on_delete=models.PROTECT, related_name="medications")
    visit = models.ForeignKey(Visit, on_delete=models.PROTECT, related_name="medications", null=True, blank=True)
    medication = models.CharField(max_length=255)
    dose = models.CharField(max_length=100, blank=True)
    route = models.CharField(max_length=100, blank=True)
    frequency = models.CharField(max_length=100, blank=True)
    duration = models.CharField(max_length=100, blank=True)
    reason = models.CharField(max_length=500, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.CURRENT)
    prescribed_by_staff = models.ForeignKey(
        HospitalStaffProfile,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="prescribed_medications",
    )
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        db_table = "medications"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["patient", "status"]),
            models.Index(fields=["patient", "created_at"]),
        ]

    def clean(self):
        errors = {}
        if self.visit_id and self.visit.patient_id != self.patient_id:
            errors["visit"] = "Medication visit must belong to the same patient."
        if self.prescribed_by_staff_id and self.visit_id:
            if self.prescribed_by_staff.hospital_id != self.visit.hospital_id:
                errors["prescribed_by_staff"] = "Prescribing staff must belong to the visit hospital."
        if self.visit_id and self.visit.status == Visit.Status.CHECKED_OUT:
            errors["visit"] = "Medication cannot be added to a checked-out visit."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Medication records are append-only and cannot be edited.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Medication records are append-only and cannot be deleted.")

    def __str__(self):
        return f"{self.medication} — {self.patient.full_name} ({self.status})"
