"""
The /api/v1 JSON envelope, identical to the Laravel reference (laravel/app/Support/ApiResponse.php
and ErrorCode.php), which customers integrate with:

    success: {"success": true,  "data": ..., "meta": {"requestId": "req_..."}}
    error:   {"success": false, "error": {"code", "message", "details"?}, "meta": {"requestId"}}

Error codes are part of the public contract: only add codes, never rename them.
"""

import logging
import secrets
import string
from enum import Enum

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404, JsonResponse
from rest_framework import exceptions

log = logging.getLogger(__name__)

_ID_ALPHABET = string.ascii_letters + string.digits


class ErrorCode(str, Enum):
    INVALID_REQUEST = "INVALID_REQUEST"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    UNAUTHORIZED = "UNAUTHORIZED"
    INVALID_API_KEY = "INVALID_API_KEY"
    FORBIDDEN = "FORBIDDEN"
    INSUFFICIENT_SCOPE = "INSUFFICIENT_SCOPE"
    ACCOUNT_SUSPENDED = "ACCOUNT_SUSPENDED"
    EMAIL_NOT_VERIFIED = "EMAIL_NOT_VERIFIED"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"
    RATE_LIMITED = "RATE_LIMITED"
    INSUFFICIENT_BALANCE = "INSUFFICIENT_BALANCE"
    INVALID_RECIPIENT = "INVALID_RECIPIENT"
    SENDER_ID_NOT_APPROVED = "SENDER_ID_NOT_APPROVED"
    CONTENT_BLOCKED = "CONTENT_BLOCKED"
    MESSAGE_TOO_LONG = "MESSAGE_TOO_LONG"
    RECIPIENT_SUPPRESSED = "RECIPIENT_SUPPRESSED"
    QUIET_HOURS = "QUIET_HOURS"
    DAILY_LIMIT_EXCEEDED = "DAILY_LIMIT_EXCEEDED"
    MONTHLY_LIMIT_EXCEEDED = "MONTHLY_LIMIT_EXCEEDED"
    PAYMENT_FAILED = "PAYMENT_FAILED"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    PROVIDER_NOT_CONFIGURED = "PROVIDER_NOT_CONFIGURED"
    FEATURE_DISABLED = "FEATURE_DISABLED"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    INTERNAL_ERROR = "INTERNAL_ERROR"

    @property
    def status(self):
        return _STATUS[self]


_STATUS = {
    ErrorCode.INVALID_REQUEST: 400,
    **dict.fromkeys([ErrorCode.VALIDATION_ERROR, ErrorCode.INVALID_RECIPIENT, ErrorCode.SENDER_ID_NOT_APPROVED,
                     ErrorCode.CONTENT_BLOCKED, ErrorCode.MESSAGE_TOO_LONG, ErrorCode.RECIPIENT_SUPPRESSED,
                     ErrorCode.QUIET_HOURS], 422),
    **dict.fromkeys([ErrorCode.UNAUTHORIZED, ErrorCode.INVALID_API_KEY], 401),
    **dict.fromkeys([ErrorCode.FORBIDDEN, ErrorCode.INSUFFICIENT_SCOPE, ErrorCode.ACCOUNT_SUSPENDED,
                     ErrorCode.EMAIL_NOT_VERIFIED, ErrorCode.FEATURE_DISABLED], 403),
    ErrorCode.NOT_FOUND: 404,
    **dict.fromkeys([ErrorCode.CONFLICT, ErrorCode.IDEMPOTENCY_CONFLICT], 409),
    **dict.fromkeys([ErrorCode.RATE_LIMITED, ErrorCode.DAILY_LIMIT_EXCEEDED, ErrorCode.MONTHLY_LIMIT_EXCEEDED], 429),
    **dict.fromkeys([ErrorCode.INSUFFICIENT_BALANCE, ErrorCode.PAYMENT_FAILED], 402),
    ErrorCode.PROVIDER_ERROR: 502,
    **dict.fromkeys([ErrorCode.PROVIDER_NOT_CONFIGURED, ErrorCode.SERVICE_UNAVAILABLE], 503),
    ErrorCode.INTERNAL_ERROR: 500,
}
assert set(_STATUS) == set(ErrorCode)


class ApiError(Exception):
    """Raise anywhere in a view or service to answer with this error."""

    def __init__(self, code, message, status=None, details=None):
        super().__init__(message)
        self.code, self.message, self.status, self.details = ErrorCode(code), message, status, details


def new_request_id():
    return "req_" + "".join(secrets.choice(_ID_ALPHABET) for _ in range(16))


def request_id(request):
    rid = getattr(request, "request_id", None)
    if not rid:
        rid = request.request_id = new_request_id()
    return rid


def _json(request, body, status):
    response = JsonResponse(body, status=status, json_dumps_params={"ensure_ascii": False})
    response["X-Request-Id"] = request_id(request)
    response["Cache-Control"] = "no-store"
    return response


def ok(request, data=None, status=200, meta=None):
    return _json(request, {"success": True, "data": data, "meta": {"requestId": request_id(request)} | (meta or {})}, status)


def fail(request, code, message, status=None, details=None):
    code = ErrorCode(code)
    error = {"code": code.value, "message": message}
    if details is not None:
        error["details"] = details
    return _json(request, {"success": False, "error": error, "meta": {"requestId": request_id(request)}}, status or code.status)


def exception_handler(exc, context):
    """DRF errors in the envelope. Anything unexpected is logged and answered with INTERNAL_ERROR."""
    request = context["request"]
    if isinstance(exc, ApiError):
        return fail(request, exc.code, exc.message, exc.status, exc.details)
    if isinstance(exc, exceptions.ValidationError):
        return fail(request, ErrorCode.VALIDATION_ERROR, "The request is invalid.", details=exc.detail)
    if isinstance(exc, exceptions.ParseError):
        return fail(request, ErrorCode.INVALID_REQUEST, "The request body is not valid JSON.")
    if isinstance(exc, (exceptions.NotAuthenticated, exceptions.AuthenticationFailed)):
        return fail(request, ErrorCode.UNAUTHORIZED, "Authentication required.")
    if isinstance(exc, (exceptions.PermissionDenied, DjangoPermissionDenied)):
        return fail(request, ErrorCode.FORBIDDEN, "You don't have permission to do this.")
    if isinstance(exc, (exceptions.NotFound, Http404)):
        return fail(request, ErrorCode.NOT_FOUND, "Not found.")
    if isinstance(exc, exceptions.MethodNotAllowed):
        return fail(request, ErrorCode.INVALID_REQUEST, "Method not allowed.", 405)
    if isinstance(exc, exceptions.Throttled):
        response = fail(request, ErrorCode.RATE_LIMITED, "Too many requests. Try again later.")
        if exc.wait:
            response["Retry-After"] = str(int(exc.wait))
        return response
    log.exception("Unhandled API error (request %s)", request_id(request))
    return fail(request, ErrorCode.INTERNAL_ERROR, "Something went wrong.")
