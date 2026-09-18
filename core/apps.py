from django.apps import AppConfig


class CoreConfig(AppConfig):
    """
    Shared, non-domain-specific code used across the whole API:
    - responses.py  — the standard success/error envelope
    - exceptions.py — the global DRF exception handler
    - messages.py   — all user-facing copy, reviewable in one place
    - audit.py      — structured logging for auth-relevant events

    Deliberately has no models — if this ever needs one (e.g. a real
    AuditLog table instead of just log lines), that's a sign it should
    probably become its own app rather than growing inside `core`.
    """
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
