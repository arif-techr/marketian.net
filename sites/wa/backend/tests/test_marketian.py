"""Signing in with the Marketian account (accounts.marketian.net over OpenID Connect)."""
from urllib.parse import parse_qs, urlsplit

import pytest
from allauth.socialaccount.models import SocialAccount
from django.contrib.auth import get_user_model
from django.test import Client
from rest_framework.test import APIClient

from apps.core import marketian

pytestmark = pytest.mark.django_db
User = get_user_model()
SERVER = "https://accounts.test/o"
CLAIMS = {"sub": "42", "email": "jane@example.com", "email_verified": True, "name": "Jane Doe", "preferred_username": "jane"}


class FakeResponse:
    def __init__(self, data):
        self._data = data
        self.status_code = 200
        self.headers = {"content-type": "application/json"}
        self.text = "{}"
        self.content = b"{}"

    def json(self):
        return self._data

    def raise_for_status(self):
        pass


class FakeAccountsServer:
    """Stands in for accounts.marketian.net: discovery, token and userinfo endpoints."""

    def __init__(self, claims):
        self.claims = claims

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get(self, url, **kwargs):
        if url.endswith("/.well-known/openid-configuration"):
            return FakeResponse({
                "issuer": SERVER,
                "authorization_endpoint": f"{SERVER}/authorize/",
                "token_endpoint": f"{SERVER}/token/",
                "userinfo_endpoint": f"{SERVER}/userinfo/",
                "jwks_uri": f"{SERVER}/.well-known/jwks.json",
                "token_endpoint_auth_methods_supported": ["client_secret_post"],
            })
        assert url == f"{SERVER}/userinfo/"
        return FakeResponse(self.claims)

    def request(self, method, url, **kwargs):
        assert url == f"{SERVER}/token/"
        return FakeResponse({"access_token": "token", "token_type": "Bearer"})


@pytest.fixture
def sso(settings, monkeypatch):
    settings.MARKETIAN_SSO = True
    settings.ACCOUNTS_URL = "https://accounts.test"
    settings.SOCIALACCOUNT_PROVIDERS = {"openid_connect": {"OAUTH_PKCE_ENABLED": True, "APPS": [{
        "provider_id": "marketian", "name": "Marketian", "client_id": "wa", "secret": "secret",
        "settings": {"server_url": SERVER},
    }]}}
    server = FakeAccountsServer(dict(CLAIMS))
    monkeypatch.setattr(marketian.SocialAccountAdapter, "get_requests_session", lambda self: server)
    return server


def sign_in_with_marketian(browser):
    """Press "Continue with Marketian account", then come back from accounts.marketian.net."""
    browser.get("/api/auth/session/")  # sets the CSRF cookie, like the app does
    start = browser.post(marketian.LOGIN_PATH, {"csrfmiddlewaretoken": browser.cookies["csrftoken"].value})
    assert start.status_code == 302 and start["Location"].startswith(f"{SERVER}/authorize/")
    state = parse_qs(urlsplit(start["Location"]).query)["state"][0]
    return browser.get("/accounts/oidc/marketian/login/callback/", {"code": "abc", "state": state})


def test_session_says_how_to_sign_in(sso, settings):
    settings.ALLOW_SIGNUP = True
    data = APIClient().get("/api/auth/session/").json()
    assert data["marketian"] == {"enabled": True, "login_url": marketian.LOGIN_PATH, "account_url": "https://accounts.test/"}
    assert data["signup_enabled"] is False  # people sign up for a Marketian account instead


def test_without_marketian_account_the_password_sign_in_is_unchanged(settings):
    data = APIClient().get("/api/auth/session/").json()
    assert data["marketian"]["enabled"] is False


def test_sign_up_form_is_off_with_marketian_account(sso, settings):
    settings.ALLOW_SIGNUP = True
    r = APIClient().post("/api/auth/register/", {"username": "bob", "password": "a-long-test-password"}, format="json")
    assert r.status_code == 403
    assert not User.objects.filter(username="bob").exists()


def test_new_marketian_user_gets_a_workspace_when_signup_is_open(sso, settings):
    settings.ALLOW_SIGNUP = True
    browser = Client()
    done = sign_in_with_marketian(browser)
    assert done.status_code == 302 and done["Location"] == "/"
    user = browser.get("/api/auth/session/").json()["user"]
    assert user["name"] == "Jane Doe"
    assert user["sign_in"] == "marketian"
    assert user["is_owner"] is True
    assert User.objects.get(id=user["id"]).email == "jane@example.com"


def test_new_marketian_user_is_turned_away_when_signup_is_closed(sso):
    browser = Client()
    page = sign_in_with_marketian(browser)
    assert page.status_code == 200
    assert b"You haven't been added yet" in page.content
    assert not User.objects.filter(email="jane@example.com").exists()
    assert browser.get("/api/auth/session/").json()["user"] is None


def test_user_added_by_the_admin_signs_in_with_their_marketian_account(sso):
    added = User.objects.create_user("jane-office", email="jane@example.com")
    browser = Client()
    assert sign_in_with_marketian(browser)["Location"] == "/"
    assert browser.get("/api/auth/session/").json()["user"]["id"] == added.id
    assert SocialAccount.objects.filter(user=added, provider="marketian").exists()


def test_unverified_email_never_takes_over_an_existing_user(sso):
    User.objects.create_user("jane-office", email="jane@example.com")
    sso.claims["email_verified"] = False
    browser = Client()
    sign_in_with_marketian(browser)
    assert not SocialAccount.objects.exists()
    assert browser.get("/api/auth/session/").json()["user"] is None


def test_sign_out_also_signs_out_of_the_marketian_account(sso, settings):
    settings.ALLOW_SIGNUP = True
    browser = Client()
    sign_in_with_marketian(browser)
    r = browser.post("/api/auth/logout/", HTTP_X_CSRFTOKEN=browser.cookies["csrftoken"].value)
    assert r.json()["redirect"] == "https://accounts.test/accounts/logout/?next=http%3A%2F%2Ftestserver%2F"
    assert browser.get("/api/auth/session/").json()["user"] is None


def test_password_sign_out_stays_here(client):
    assert client.post("/api/auth/logout/").json()["redirect"] is None


def test_marketian_users_change_their_password_at_the_account(sso, settings):
    settings.ALLOW_SIGNUP = True
    browser = Client()
    sign_in_with_marketian(browser)
    r = browser.post("/api/auth/password/", {"current_password": "x", "new_password": "a-new-long-password"},
                     content_type="application/json", HTTP_X_CSRFTOKEN=browser.cookies["csrftoken"].value)
    assert r.status_code == 400
    assert "Marketian account" in r.json()["error"]


def test_team_members_still_sign_in_with_a_password(sso, user):
    r = APIClient().post("/api/auth/login/", {"username": user.username, "password": "a-long-test-password"}, format="json")
    assert r.status_code == 200
    assert r.json()["user"]["sign_in"] == "password"
