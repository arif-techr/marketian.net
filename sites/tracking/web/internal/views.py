"""
Endpoints for the server itself, never the public: Caddy answers 404 for /internal/*
on tracking.marketian.net and calls these over the Docker network.
"""

from django.db import connection
from django.http import HttpResponse, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from tracker.models import Domain


@never_cache
@require_GET
def caddy_ask(request):
    """Caddy asks before getting a certificate for a client host (on-demand TLS).
    200 only for a verified (or recently failing) domain; anything else gets 404,
    so nobody can make us request certificates for random names."""
    hostname = request.GET.get("domain", "").strip().lower().rstrip(".")
    domain = Domain.objects.filter(hostname=hostname).only("status").first() if hostname else None
    if domain is None or not domain.serves_events:
        return HttpResponse(status=404)
    return HttpResponse("ok")


@never_cache
@require_GET
def healthz(request):
    """For the Docker healthcheck: 200 when the database answers."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:
        return JsonResponse({"ok": False, "database": "down"}, status=503)
    return JsonResponse({"ok": True})
