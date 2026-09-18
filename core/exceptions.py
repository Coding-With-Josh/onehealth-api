"""
Global exception handler for the whole API.

WHY: DRF's default behaviour returns a different shape for every kind of
error — `{"detail": "..."}` for auth/permission errors, `{"field": [...]}`
for validation errors, and (worst of all) Django's raw debug page or a
bare 500 with no body at all for anything unhandled. That's both
inconsistent for the frontend AND a security problem: an unhandled
exception can leak a stack trace, a SQL fragment, an internal file path,
or a third-party library's internal error text straight into the API
response — none of which should ever reach a client, especially on a
system holding medical records.

This handler is wired in via REST_FRAMEWORK["EXCEPTION_HANDLER"]
(see settings_snippet.py) and guarantees:

  1. EVERY error response — expected (bad input, wrong permissions) or
     unexpected (a bug) — comes back in the same envelope shape as
     core.responses.error_response(), so the frontend has exactly one
     error-handling code path.
  2. A stable, machine-readable `code` the frontend can branch on
     (e.g. show a "change your password" screen on MUST_CHANGE_PASSWORD)
     without parsing message text, which might change wording over time.
  3. `message` is always safe to show a user — for anything unexpected,
     the real exception is logged server-side (with a stack trace) and a
     generic, non-leaking message goes to the client instead.
  4. Field-level validation errors (e.g. {"email": ["..."]}) are still
     passed through under `errors`, since those ARE meant to be read and
     acted on by the caller (that's the whole point of form validation) —
     only the top-level shape changes, not the useful detail.
"""

import logging

from rest_framework import exceptions as drf_exceptions
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_default_exception_handler

from .messages import GENERIC

logger = logging.getLogger("onehealth.api")

# Maps a DRF/library exception type to a stable, machine-readable code.
# Add new exception types here as the project grows — never let a new
# exception type fall through to a bare "ERROR" code without a conscious
# decision about what message it should carry.
_EXCEPTION_CODE_MAP = {
    drf_exceptions.ValidationError: ("VALIDATION_ERROR", GENERIC["VALIDATION_ERROR"]),
    drf_exceptions.AuthenticationFailed: ("AUTHENTICATION_FAILED", None),  # message comes from the exception itself
    drf_exceptions.NotAuthenticated: ("NOT_AUTHENTICATED", GENERIC["NOT_AUTHENTICATED"]),
    drf_exceptions.PermissionDenied: ("PERMISSION_DENIED", None),  # our permission classes set a specific, safe message
    drf_exceptions.NotFound: ("NOT_FOUND", GENERIC["NOT_FOUND"]),
    drf_exceptions.MethodNotAllowed: ("METHOD_NOT_ALLOWED", GENERIC["METHOD_NOT_ALLOWED"]),
    drf_exceptions.Throttled: ("RATE_LIMITED", None),  # built dynamically below to include wait time
    drf_exceptions.ParseError: ("PARSE_ERROR", GENERIC["PARSE_ERROR"]),
    drf_exceptions.UnsupportedMediaType: ("UNSUPPORTED_MEDIA_TYPE", GENERIC["UNSUPPORTED_MEDIA_TYPE"]),
    drf_exceptions.NotAcceptable: ("NOT_ACCEPTABLE", GENERIC["PARSE_ERROR"]),
}


def _extract_field_errors(detail):
    """
    DRF puts validation errors into response.data as e.g.
    {"email": [ErrorDetail("...")]} or ["ErrorDetail(...)"] for
    non_field_errors. Convert to a plain, JSON-clean dict/list of plain
    strings — never leak ErrorDetail's repr or code internals.
    """
    if isinstance(detail, dict):
        return {key: [str(v) for v in value] if isinstance(value, list) else str(value)
                for key, value in detail.items()}
    if isinstance(detail, list):
        return {"non_field_errors": [str(v) for v in detail]}
    return {}


def custom_exception_handler(exc, context):
    response = drf_default_exception_handler(exc, context)

    if response is None:
        # Anything DRF doesn't already know how to handle is, by
        # definition, a bug or an unexpected condition (a DB error, a
        # None where an object was assumed to exist, a third-party
        # library raising something unusual, etc). Log it in FULL,
        # server-side only, and never let any part of it reach the caller.
        view = context.get("view")
        logger.exception(
            "Unhandled exception in %s",
            getattr(view, "__class__", view),
        )
        return Response(
            {
                "success": False,
                "code": "SERVER_ERROR",
                "message": GENERIC["SERVER_ERROR"],
                "errors": {},
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    exc_type = type(exc)
    # Exact-type lookup: every DRF exception we map is a direct sibling of
    # APIException, not a subclass of each other, so this is safe. A
    # future custom exception that isn't in the map falls through to the
    # `else` branch below, which still uses whatever safe `detail` DRF
    # attached rather than inventing a message.
    code, safe_message = _EXCEPTION_CODE_MAP.get(exc_type, ("ERROR", None))

    # Throttled needs the dynamic wait time baked into the message.
    if isinstance(exc, drf_exceptions.Throttled):
        wait = getattr(exc, "wait", None)
        safe_message = (
            f"Too many attempts. Please try again in {int(wait)} seconds."
            if wait
            else GENERIC["RATE_LIMITED"]
        )

    errors = {}
    detail = response.data

    if safe_message is not None:
        # We have a pre-approved, written message for this error type —
        # use it, and treat whatever DRF put in `detail` as field-level
        # errors only (useful for e.g. VALIDATION_ERROR's per-field detail).
        if exc_type is drf_exceptions.ValidationError:
            errors = _extract_field_errors(detail)
        message = safe_message
    else:
        # AuthenticationFailed / PermissionDenied: our own code sets a
        # specific, already-safe message (see users/permissions.py and
        # simplejwt's "No active account found with the given
        # credentials" default) — pass it through as-is rather than
        # overriding with a generic one, but strip it out of `errors` so
        # it isn't duplicated.
        if isinstance(detail, dict) and set(detail.keys()) == {"detail"}:
            message = str(detail["detail"])
        elif isinstance(detail, list) and detail:
            message = str(detail[0])
        else:
            message = "Request failed."

    return Response(
        {
            "success": False,
            "code": code,
            "message": message,
            "errors": errors,
        },
        status=response.status_code,
    )
