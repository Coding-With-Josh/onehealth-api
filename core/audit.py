"""Persistent audit trail helper. Never record passwords, tokens, raw bodies, or PHI."""
from audit.models import AuditLog


def _ip(request):
    if not request:
        return None
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    return forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR")


def log_event(event: str, *, user_id=None, email=None, request=None, hospital_id=None,
              patient_id=None, target_type="", target_id="", **extra):
    actor_id = getattr(user_id, "pk", user_id) if user_id else None
    metadata = {k: str(v) for k, v in extra.items() if v is not None}
    if email:
        metadata["actor_email"] = str(email)
    return AuditLog.objects.create(
        actor_id=actor_id, hospital_id=hospital_id, patient_id=patient_id,
        action=event, target_type=target_type, target_id=str(target_id) if target_id else "",
        metadata=metadata, ip_address=_ip(request),
    )
