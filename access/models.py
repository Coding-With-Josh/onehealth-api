import secrets
import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from users.models import Hospital, HospitalStaffProfile, PatientProfile
from visits.models import Visit


class EmergencyContact(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(PatientProfile, on_delete=models.PROTECT, related_name="emergency_contacts")
    full_name = models.CharField(max_length=255)
    relationship = models.CharField(max_length=100, blank=True)
    phone_number = models.CharField(max_length=30)
    email = models.EmailField(blank=True)
    priority_order = models.PositiveSmallIntegerField(default=1)
    response_token = models.CharField(max_length=64, unique=True, editable=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "emergency_contacts"
        ordering = ["created_at"]

    def save(self, *args, **kwargs):
        if not self.response_token:
            self.response_token = secrets.token_urlsafe(32)
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.full_name} — {self.patient.full_name}"


class AccessRequest(models.Model):
    class RequestType(models.TextChoices):
        NORMAL = "normal", "Normal"
        EMERGENCY = "emergency", "Emergency"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        DENIED = "denied", "Denied"
        EXPIRED = "expired", "Expired"

    class AccessLevel(models.TextChoices):
        CRITICAL_INFO_ONLY = "critical_info_only", "Critical information only"
        FULL_RECORD = "full_record", "Full record"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    visit = models.ForeignKey(Visit, on_delete=models.PROTECT, related_name="access_requests")
    patient = models.ForeignKey(PatientProfile, on_delete=models.PROTECT, related_name="access_requests")
    hospital = models.ForeignKey(Hospital, on_delete=models.PROTECT, related_name="access_requests")
    requested_by_staff = models.ForeignKey(
        HospitalStaffProfile, on_delete=models.PROTECT, related_name="access_requests"
    )
    request_type = models.CharField(max_length=20, choices=RequestType.choices, default=RequestType.NORMAL)
    access_level = models.CharField(max_length=30, choices=AccessLevel.choices, default=AccessLevel.FULL_RECORD)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    code = models.CharField(max_length=6, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    patient_response_deadline = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "access_requests"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["patient", "status"]),
            models.Index(fields=["hospital", "status"]),
            models.Index(fields=["visit", "status"]),
        ]

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = f"{secrets.randbelow(1000000):06d}"
        if self.patient_response_deadline is None:
            from django.conf import settings
            timeout = getattr(settings, "ACCESS_REQUEST_RESPONSE_TIMEOUT_MINUTES", 15)
            self.patient_response_deadline = timezone.now() + timezone.timedelta(minutes=timeout)
        self.full_clean()
        return super().save(*args, **kwargs)

    def clean(self):
        errors = {}
        if self.visit_id:
            if self.visit.patient_id != self.patient_id:
                errors["patient"] = "Access request patient must match the visit patient."
            if self.visit.hospital_id != self.hospital_id:
                errors["hospital"] = "Access request hospital must match the visit hospital."
        if self.requested_by_staff_id and self.requested_by_staff.hospital_id != self.hospital_id:
            errors["requested_by_staff"] = "Requesting staff must belong to the requesting hospital."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.request_type} access — {self.patient.full_name} — {self.hospital.name}"


class AccessGrant(models.Model):
    class GrantedBy(models.TextChoices):
        PATIENT = "patient", "Patient"
        EMERGENCY_CONTACT = "emergency_contact", "Emergency contact"

    class RevokedBy(models.TextChoices):
        PATIENT = "patient", "Patient"
        SYSTEM = "system", "System / checkout"
        ESCALATION = "escalation", "Escalation"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    access_request = models.OneToOneField(AccessRequest, on_delete=models.PROTECT, related_name="grant")
    access_level = models.CharField(max_length=30, choices=AccessRequest.AccessLevel.choices)
    granted_at = models.DateTimeField(default=timezone.now)
    granted_by = models.CharField(max_length=30, choices=GrantedBy.choices)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_by = models.CharField(max_length=30, choices=RevokedBy.choices, null=True, blank=True)

    class Meta:
        db_table = "access_grants"
        indexes = [models.Index(fields=["revoked_at"])]

    @property
    def is_active(self):
        return (
            self.revoked_at is None
            and self.access_request.visit.status == Visit.Status.ACTIVE
            and self.access_request.hospital.verification_status == Hospital.VerificationStatus.VERIFIED
        )

    def revoke(self, revoked_by):
        if self.revoked_at is None:
            self.revoked_at = timezone.now()
            self.revoked_by = revoked_by
            self.save(update_fields=["revoked_at", "revoked_by"])

    def __str__(self):
        return f"Grant {self.id} — {self.access_request.patient.full_name}"


class EmergencyEscalation(models.Model):
    class Stage(models.TextChoices):
        PATIENT_NOTIFIED = "patient_notified", "Patient notified"
        EMERGENCY_CONTACT_NOTIFIED = "emergency_contact_notified", "Emergency contact notified"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    access_request = models.OneToOneField(AccessRequest, on_delete=models.PROTECT, related_name="escalation")
    stage = models.CharField(max_length=40, choices=Stage.choices)
    triggered_at = models.DateTimeField(default=timezone.now)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "emergency_escalations"
        indexes = [models.Index(fields=["stage", "resolved_at"])]

    def resolve(self, resolved_by):
        self.resolved_at = timezone.now()
        self.resolved_by = str(resolved_by)
        self.save(update_fields=["resolved_at", "resolved_by"])

    def __str__(self):
        return f"Escalation — {self.access_request.patient.full_name} — {self.stage}"
