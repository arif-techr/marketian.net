from .envelope import request_id


class RequestIdMiddleware:
    """Every request gets a request ID (req_…), returned in the X-Request-Id header and the envelope.
    A request ID sent by the panel (X-Request-Id) is kept, so one action can be traced through both."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        incoming = request.headers.get("X-Request-Id", "")
        if incoming.startswith("req_") and 8 <= len(incoming) <= 64 and incoming[4:].isalnum():
            request.request_id = incoming
        response = self.get_response(request)
        response.setdefault("X-Request-Id", request_id(request))
        return response
