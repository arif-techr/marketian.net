from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount
from oauth2_provider.oauth2_validators import OAuth2Validator


class MarketianValidator(OAuth2Validator):
    """What a product learns about the person who signs in (the ID token claims)."""

    def get_additional_claims(self, request):
        user = request.user
        primary = EmailAddress.objects.filter(user=user, primary=True).first()
        github = SocialAccount.objects.filter(user=user, provider="github").first()
        return {
            "email": user.email,
            "email_verified": bool(primary and primary.verified),
            "name": user.get_full_name() or user.username,
            "preferred_username": user.username,
            "picture": github.get_avatar_url() if github else "",
        }
