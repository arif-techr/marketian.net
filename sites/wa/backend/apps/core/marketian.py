"""Sign in with the Marketian account (accounts.marketian.net, OpenID Connect via django-allauth)."""
from urllib.parse import urlencode

from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.models import SocialAccount
from django.conf import settings

PROVIDER = "marketian"
# The SPA posts a form here (with the CSRF token) to start signing in.
LOGIN_PATH = "/accounts/oidc/marketian/login/"


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    def is_open_for_signup(self, request, sociallogin):
        """A Marketian account that matches no user here only gets a new workspace when ALLOW_SIGNUP is on.
        People the admin added (a user with the same email) always get in: allauth connects them first."""
        return settings.ALLOW_SIGNUP


def uses_marketian_account(user) -> bool:
    return SocialAccount.objects.filter(user=user, provider=PROVIDER).exists()


def sign_out_url(request) -> str:
    """Also sign out of the Marketian account, then come back to this site's sign-in page."""
    back = request.build_absolute_uri("/")
    return f"{settings.ACCOUNTS_URL}/accounts/logout/?{urlencode({'next': back})}"
