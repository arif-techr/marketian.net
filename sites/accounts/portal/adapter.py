import logging
from urllib.parse import urlsplit

from allauth.account.adapter import DefaultAccountAdapter
from django.conf import settings

logger = logging.getLogger(__name__)


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

    def send_mail(self, template_prefix, email, context):
        """A mail server that is down or misconfigured must not break sign-up: log it instead."""
        try:
            super().send_mail(template_prefix, email, context)
        except Exception:
            logger.exception("Could not send %s email to %s", template_prefix, email)
