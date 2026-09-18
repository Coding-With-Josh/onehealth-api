import secrets
import uuid
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from users.models import PatientProfile


class PatientCard(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        REVOKED = "revoked", "Revoked"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(PatientProfile, on_delete=models.PROTECT, related_name="cards")
    card_reference = models.CharField(max_length=40, unique=True, editable=False)
    issued_at = models.DateTimeField(default=timezone.now, editable=False)
    renewed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)

    class Meta:
        db_table = "patient_cards"
        ordering = ["-issued_at"]
        indexes = [
            models.Index(fields=["patient", "status"]),
            models.Index(fields=["card_reference"]),
            models.Index(fields=["expires_at"]),
        ]

    def save(self, *args, **kwargs):
        if not self.card_reference:
            self.card_reference = f"OH-{secrets.token_urlsafe(18)}"
        if not self.expires_at:
            days = getattr(settings, "PATIENT_CARD_VALIDITY_DAYS", 365)
            self.expires_at = timezone.now() + timedelta(days=days)
        self.full_clean()
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            # Card lifecycle changes are intentionally explicit in the service/views.
            # Prevent arbitrary edits through model.save().
            raise ValidationError("Existing cards cannot be edited directly. Use issue, renew, or revoke actions.")
        return super().save(*args, **kwargs)

    def renew(self):
        if self.status != self.Status.ACTIVE:
            raise ValidationError("A revoked card cannot be renewed.")
        days = getattr(settings, "PATIENT_CARD_VALIDITY_DAYS", 365)
        now = timezone.now()
        self.renewed_at = now
        self.expires_at = now + timedelta(days=days)
        type(self).objects.filter(pk=self.pk).update(
            renewed_at=self.renewed_at,
            expires_at=self.expires_at,
        )
        return self

    def revoke(self):
        if self.status != self.Status.REVOKED:
            type(self).objects.filter(pk=self.pk).update(status=self.Status.REVOKED)
            self.status = self.Status.REVOKED
        return self

    @property
    def is_active(self):
        return self.status == self.Status.ACTIVE and self.expires_at > timezone.now()

    def __str__(self):
        return f"{self.card_reference} — {self.patient.full_name}"
