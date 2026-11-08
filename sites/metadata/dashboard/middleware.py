from django.utils.cache import patch_cache_control


class PreloadCacheMiddleware:
    """Let the browser keep a page fetched on hover (static/js/app.js, header HX-Preloaded)
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
