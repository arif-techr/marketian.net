"""
The admin pages (/admin/) sign in with the Marketian account too, like the rest of the site:
no separate admin password. Marketian accounts whose email is in ADMIN_EMAILS (settings, from
.env) are made staff each time they sign in; take an email out of the list and that person
loses admin access at their next sign-in.

Wired up in urls.py (admin.site.login) and apps.py (the sign-in signal). The portfolio has no
customer accounts, so SignupOnlyForAdmins also stops anyone else's Marketian sign-in from
creating an account here.
"""

from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings
from django.contrib import admin
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme


def is_admin_email(email):
    return bool(email) and email.strip().lower() in settings.ADMIN_EMAILS


def sync_staff(sender, request, user, sociallogin=None, **kwargs):
    """On every sign-in with the Marketian account: staff and superuser exactly when the email is
    listed in ADMIN_EMAILS. Other logins (a superuser made with createsuperuser) are left alone."""
    if sociallogin is None:
        return
    allowed = is_admin_email(user.email)
    if user.is_staff != allowed or user.is_superuser != allowed:
        user.is_staff = user.is_superuser = allowed
        user.save(update_fields=["is_staff", "is_superuser"])


def admin_login(request, extra_context=None):
    """Replaces the admin's username/password form."""
    next_url = request.GET.get(REDIRECT_FIELD_NAME, "") or request.POST.get(REDIRECT_FIELD_NAME, "")
    if not url_has_allowed_host_and_scheme(next_url, {request.get_host()}, request.is_secure()):
        next_url = reverse("admin:index")
    if request.user.is_authenticated and request.user.is_active and request.user.is_staff:
        return redirect(next_url)
    denied = request.user.is_authenticated  # signed in, but not on the ADMIN_EMAILS list
    context = admin.site.each_context(request) | {"title": "Sign in", "next": next_url, "denied": denied}
    return render(request, "admin/marketian_login.html", context | (extra_context or {}), status=403 if denied else 200)


class SignupOnlyForAdmins(DefaultSocialAccountAdapter):
    """Only the emails in ADMIN_EMAILS get an account here (visitors never sign in)."""

    def is_open_for_signup(self, request, sociallogin):
        return is_admin_email(sociallogin.user.email)
