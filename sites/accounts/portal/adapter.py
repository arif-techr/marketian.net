from urllib.parse import urlsplit

from allauth.account.adapter import DefaultAccountAdapter
from django.conf import settings


class AccountAdapter(DefaultAccountAdapter):
    def is_safe_url(self, url):
        """Also allow sending people back to any product (https://*.marketian.net)."""
        if super().is_safe_url(url):
            return True
        parts = urlsplit(url or "")
        host = (parts.hostname or "").lower()
        domain = settings.PRODUCTS_DOMAIN
        # Plain http only where cookies aren't https-only, i.e. local testing.
        schemes = ("https",) if settings.SESSION_COOKIE_SECURE else ("https", "http")
        return parts.scheme in schemes and (host == domain or host.endswith("." + domain))
