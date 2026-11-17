import logging

from django.db import connection

from .envelope import ErrorCode, fail, ok

log = logging.getLogger(__name__)


def health(request):
    """GET /api/v1/health: public liveness + a database round trip. No infrastructure details."""
    if request.method not in ("GET", "HEAD"):
        return fail(request, ErrorCode.INVALID_REQUEST, "Method not allowed.", 405)
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:
        log.exception("Health check: database unavailable")
        return fail(request, ErrorCode.INTERNAL_ERROR, "Service unavailable.", 503)
    return ok(request, {"status": "ok", "database": "ok"})


def not_found(request, exception=None):
    return fail(request, ErrorCode.NOT_FOUND, "Not found.")


def server_error(request):
    return fail(request, ErrorCode.INTERNAL_ERROR, "Something went wrong.")
