from django.conf import settings
from django.http import HttpResponsePermanentRedirect


class CanonicalDomainMiddleware:
    """Send every alias domain (marketain.net, www.*) to the one canonical host."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        canonical = getattr(settings, "CANONICAL_HOST", "")
        if canonical:
            host = request.get_host().split(":")[0].lower()
            if host != canonical and host not in ("localhost", "127.0.0.1"):
                scheme = "https" if not settings.DEBUG else request.scheme
                return HttpResponsePermanentRedirect(f"{scheme}://{canonical}{request.get_full_path()}")
        return self.get_response(request)
