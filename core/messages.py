"""
All user-facing copy for the auth module lives here — nowhere else.

WHY: this is a medical system. A vague or inconsistent error message
("Bad request", "Error", a raw stack trace) is how a patient or a nurse
ends up retrying a broken action, submitting a form five times, or
giving up on something that actually needed their attention (e.g. a
temp-password change that's mandatory before they can do anything else).

Keeping every message in one file means:
  1. A non-engineer (product, clinical safety reviewer) can read and sign
     off on the exact wording in one pass, without hunting through views.
  2. Nobody accidentally lets a raw exception/library string reach the
     client — every message here is *written*, not generated.
  3. Wording stays consistent (e.g. we always say "You'll need to..."
     rather than mixing tones across endpoints).

RULE: a message here must be true, specific enough to act on, and safe
to show to *anyone* who might receive it — including someone who is not
supposed to have access (see the AUTH_* messages below, which are
deliberately generic to avoid confirming whether an email/account
exists — this is a security requirement, not an oversight).
"""

AUTH = {
    "LOGIN_SUCCESS": "Login successful.",
    "LOGOUT_SUCCESS": "You have been logged out.",
    "LOGOUT_MISSING_TOKEN": "A refresh token is required to log out.",
    "LOGOUT_INVALID_TOKEN": "This session is already invalid or has expired. You're effectively logged out.",
    "TOKEN_REFRESHED": "Session refreshed.",
    # Deliberately generic — do not change to "wrong password" / "no such
    # account" / "account disabled". Confirming which one it was tells an
    # attacker whether an email address is registered on the platform.
    "INVALID_CREDENTIALS": "The email or password you entered is incorrect.",
    "MUST_CHANGE_PASSWORD": "You must change your temporary password before you can continue.",
}

REGISTRATION = {
    "PATIENT_REGISTERED": "Your account has been created. You can now log in.",
    "DEPENDENT_REGISTERED": "The dependent's record has been created.",
    "HOSPITAL_REGISTERED": (
        "Your hospital has been registered and is pending verification. "
        "You won't be able to access patient records until an administrator "
        "verifies your hospital."
    ),
    "STAFF_CREATED": (
        "The staff account has been created. A temporary password has been "
        "generated and will be sent to them separately — it is not included "
        "in this response."
    ),
    "EMAIL_TAKEN": "An account with this email address already exists.",
    "REGISTRATION_NUMBER_TAKEN": "A hospital with this registration number is already registered.",
}

PASSWORD = {
    "CHANGED": "Your password has been updated.",
    "WRONG_OLD_PASSWORD": "Your current password is incorrect.",
    # Same email-enumeration concern as INVALID_CREDENTIALS above — this
    # response must be identical whether or not the email exists.
    "RESET_REQUESTED": "If an account with that email exists, a password reset link has been sent to it.",
    "RESET_LINK_INVALID": "This password reset link is invalid. Please request a new one.",
    "RESET_LINK_EXPIRED": "This password reset link has expired. Please request a new one.",
    "RESET_SUCCESS": "Your password has been reset. You can now log in with your new password.",
}

PROFILE = {
    "FETCHED": "Profile retrieved.",
}

GENERIC = {
    "VALIDATION_ERROR": "Some of the information you provided is invalid or incomplete.",
    "NOT_AUTHENTICATED": "You need to be logged in to do that.",
    "PERMISSION_DENIED": "You don't have permission to perform this action.",
    "NOT_FOUND": "We couldn't find what you're looking for.",
    "METHOD_NOT_ALLOWED": "This action isn't supported on this endpoint.",
    "RATE_LIMITED": "Too many attempts. Please wait before trying again.",
    "PARSE_ERROR": "We couldn't understand the request you sent — please check the request format.",
    "UNSUPPORTED_MEDIA_TYPE": "That content type isn't supported by this endpoint.",
    # Deliberately generic. The real cause is always logged server-side
    # (see core/exceptions.py) but NEVER returned to the client — an
    # unhandled exception can easily contain internal details (query
    # fragments, file paths, third-party error text) that must not leak
    # from a medical system's API.
    "SERVER_ERROR": (
        "Something went wrong on our end. Please try again in a moment. "
        "If this keeps happening, contact support and mention the time this occurred."
    ),
}
