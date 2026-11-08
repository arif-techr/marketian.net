from urllib.parse import urlencode

from allauth.socialaccount.models import SocialAccount
from django.conf import settings
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme


def landing(request):
    return render(request, "dashboard/landing.html")


def login(request):
    """One button: continue with the Marketian account (GitHub or email)."""
    next_url = request.GET.get("next", "")
    if not url_has_allowed_host_and_scheme(next_url, {request.get_host()}, request.is_secure()):
        next_url = ""
    if request.user.is_authenticated:
        return redirect(next_url or "dashboard:app")
    return render(request, "dashboard/login.html", {"next": next_url})


def logout(request):
    """Sign out here and of the Marketian account, then come back to this product's home page."""
    auth_logout(request)
    back = request.build_absolute_uri("/")
    return redirect(f"{settings.ACCOUNTS_URL}/accounts/logout/?{urlencode({'next': back})}")


@login_required
def app(request):
    account = SocialAccount.objects.filter(user=request.user, provider="marketian").first()
    # allauth keeps the Marketian account's details under "userinfo" (and the raw "id_token").
    profile = (account.extra_data if account else {}).get("userinfo", {})
    return render(request, "dashboard/app.html", {
        "display_name": request.user.get_full_name() or profile.get("name") or request.user.email,
        "picture": profile.get("picture", ""),
    })
