"""
Standard API response envelope.

WHY THIS FILE EXISTS
---------------------
Plain DRF `Response(serializer.data)` calls mean every endpoint returns a
differently-shaped body: sometimes a bare object, sometimes a list,
sometimes `{"detail": "..."}`. For a frontend team (or anyone reading
Swagger docs) that means "check every endpoint individually to know what
you'll get back" — the same problem Laravel solves with API Resources /
`response()->json([...])` conventions.

This module is the one place that decides the shape. EVERY endpoint in
this project should return `success_response(...)` or `error_response(...)`
— never a bare `Response(...)` — so the frontend can write one generic
response parser instead of one per endpoint.

SHAPE
-----
Success:
    {
        "success": true,
        "message": "Human-readable, safe-to-display summary.",
        "data": { ... } | [ ... ] | null,
        "meta": { ... }            # optional — pagination, counts, etc.
    }

Error (see core.exceptions for how these get generated automatically
from raised exceptions — you rarely need to call error_response by hand,
but it's here for the few places a view needs to fail early, e.g. a
missing required field on an APIView-style function):
    {
        "success": false,
        "code": "VALIDATION_ERROR",   # stable, machine-readable — safe for
                                       # the frontend to switch/branch on
        "message": "Human-readable, safe-to-display summary.",
        "errors": { "field": ["This field is required."] }   # optional
    }

`message` is ALWAYS written to be safely shown to an end user directly —
never a raw exception string, stack trace, or library-internal detail.
See core/messages.py for the approved copy and core/exceptions.py for
the rule that enforces this centrally.
"""

from rest_framework.response import Response


def success_response(data=None, message="Request successful.", status_code=200, meta=None):
    payload = {
        "success": True,
        "message": message,
        "data": data,
    }
    if meta is not None:
        payload["meta"] = meta
    return Response(payload, status=status_code)


def error_response(message="Request failed.", errors=None, status_code=400, code="ERROR"):
    return Response(
        {
            "success": False,
            "code": code,
            "message": message,
            "errors": errors or {},
        },
        status=status_code,
    )
