from django.conf import settings
from django.http import HttpResponsePermanentRedirect
from django.utils.cache import patch_cache_control


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


class PreloadCacheMiddleware:
    """Let the browser keep a page fetched on hover (htmx preload, header HX-Preloaded)
    for a few seconds, so the click that follows opens it instantly."""

    MAX_AGE = 10

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        messages = getattr(request, "_messages", None)
        if (
            request.method == "GET"
            and request.headers.get("HX-Preloaded") == "true"
            and response.status_code == 200
            and not response.has_header("Cache-Control")
            and not (messages is not None and messages.used)  # a one-time notice was shown: never reuse
        ):
            patch_cache_control(response, private=True, max_age=self.MAX_AGE)
        return response
