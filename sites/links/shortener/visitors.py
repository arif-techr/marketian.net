"""What a click's request says about the visitor: device, browser, where they came from.

Just enough User-Agent reading for click stats, without another dependency.
"""
import hashlib
import re
from urllib.parse import urlsplit

from django.conf import settings
from django.utils import timezone

# Link previews (WhatsApp, Facebook, Slack...), search engines and scripts: they are sent on
# like anyone else, but don't count as clicks.
BOTS = re.compile(
    r"bot|crawl|spider|slurp|preview|facebookexternalhit|whatsapp|telegram|skype|slack|discord|"
    r"embedly|curl|wget|python-|go-http|java/|okhttp|headless",
    re.IGNORECASE,
)
BROWSERS = [("Edge", r"Edg/|Edge/"), ("Opera", r"OPR/|Opera"), ("Samsung Internet", r"SamsungBrowser"),
            ("Firefox", r"Firefox|FxiOS"), ("Chrome", r"Chrome|CriOS"), ("Safari", r"Safari")]
SYSTEMS = [("Windows", r"Windows"), ("iOS", r"iPhone|iPad|iPod"), ("Android", r"Android"),
           ("macOS", r"Macintosh|Mac OS X"), ("ChromeOS", r"CrOS"), ("Linux", r"Linux")]


def user_agent(request):
    return request.META.get("HTTP_USER_AGENT", "")


def is_bot(ua):
    return not ua or bool(BOTS.search(ua))


def device(ua):
    if re.search(r"iPad|Tablet", ua) or (re.search(r"Android", ua) and not re.search(r"Mobile", ua)):
        return "Tablet"
    if re.search(r"Mobi|iPhone|Android", ua):
        return "Mobile"
    return "Desktop"


def first_match(ua, table):
    return next((name for name, pattern in table if re.search(pattern, ua)), "Other")


def referrer_domain(request):
    host = (urlsplit(request.META.get("HTTP_REFERER", "")).hostname or "").lower()
    return host.removeprefix("www.")[:200]


def client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR", "")


def visitor_id(request):
    """Same value for the same visitor all day, a different one tomorrow; the IP can't be read back."""
    raw = f"{settings.SECRET_KEY}|{timezone.localdate()}|{client_ip(request)}|{user_agent(request)}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]
