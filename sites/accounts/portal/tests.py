from io import StringIO

from allauth.account.models import EmailAddress
from allauth.core import context
from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from oauth2_provider.models import get_application_model

from .adapter import AccountAdapter
from .oidc import MarketianValidator

Application = get_application_model()
User = get_user_model()


def register(*args):
    out = StringIO()
    call_command("register_product", *args, stdout=out)
    return out.getvalue()


class RegisterProductTests(TestCase):
    def test_registers_a_product(self):
        out = register("metadata", "https://metadata.marketian.net/")
        app = Application.objects.get(name="metadata")
        self.assertIn(f"MARKETIAN_CLIENT_ID={app.client_id}", out)
        self.assertIn("MARKETIAN_CLIENT_SECRET=", out)
        self.assertEqual(app.redirect_uris, "https://metadata.marketian.net/accounts/oidc/marketian/login/callback/")
        self.assertEqual(app.post_logout_redirect_uris, "https://metadata.marketian.net/")
        self.assertTrue(app.skip_authorization)
        self.assertEqual(app.algorithm, Application.RS256_ALGORITHM)

    def test_refuses_a_second_registration(self):
        register("metadata", "https://metadata.marketian.net")
        with self.assertRaises(CommandError):
            register("metadata", "https://metadata.marketian.net")

    def test_reset_secret_keeps_the_client_id(self):
        register("metadata", "https://metadata.marketian.net")
        client_id = Application.objects.get(name="metadata").client_id
        out = register("metadata", "https://metadata.marketian.net", "--reset-secret")
        self.assertIn(f"MARKETIAN_CLIENT_ID={client_id}", out)
        self.assertEqual(Application.objects.filter(name="metadata").count(), 1)

    def test_rejects_an_address_without_scheme(self):
        with self.assertRaises(CommandError):
            register("metadata", "metadata.marketian.net")


@override_settings(PRODUCTS_DOMAIN="marketian.net", SESSION_COOKIE_SECURE=True)
class SafeRedirectTests(TestCase):
    """Sign-in and sign-out may send people back to a product, and nowhere else."""

    def setUp(self):
        request = RequestFactory().get("/", HTTP_HOST="accounts.marketian.net", secure=True)
        self.adapter = AccountAdapter(request)
        # allauth reads the current request from its own context.
        request_context = context.request_context(request)
        request_context.__enter__()
        self.addCleanup(request_context.__exit__, None, None, None)

    def test_products_are_allowed(self):
        for url in ["https://metadata.marketian.net/", "https://marketian.net/", "https://qr.marketian.net/app/"]:
            with self.subTest(url=url):
                self.assertTrue(self.adapter.is_safe_url(url))

    def test_other_sites_are_refused(self):
        for url in [
            "https://evil.example/",
            "https://marketian.net.evil.example/",
            "https://evilmarketian.net/",
            "http://metadata.marketian.net/",  # plain http when cookies are https-only
            "javascript:alert(1)",
            "",
        ]:
            with self.subTest(url=url):
                self.assertFalse(self.adapter.is_safe_url(url))


class PortalTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("jane", "jane@example.com", "a-long-password-1", first_name="Jane", last_name="Doe")
        EmailAddress.objects.create(user=self.user, email="jane@example.com", primary=True, verified=True)

    def test_home_needs_sign_in(self):
        response = self.client.get(reverse("portal:home"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("account_login"), response["Location"])

    def test_home_lists_products(self):
        register("metadata", "https://metadata.marketian.net")
        self.client.force_login(self.user)
        response = self.client.get(reverse("portal:home"))
        self.assertContains(response, "Jane Doe")
        self.assertContains(response, 'href="https://metadata.marketian.net/"')

    def test_sign_in_pages_render(self):
        for name in ["account_login", "account_signup"]:
            with self.subTest(page=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)

    def test_id_token_claims(self):
        request = RequestFactory().get("/")
        request.user = self.user
        claims = MarketianValidator().get_additional_claims(request)
        self.assertEqual(claims["email"], "jane@example.com")
        self.assertTrue(claims["email_verified"])
        self.assertEqual(claims["name"], "Jane Doe")
        self.assertEqual(claims["picture"], "")

    def test_openid_discovery(self):
        response = self.client.get("/o/.well-known/openid-configuration")
        self.assertEqual(response.status_code, 200)
        self.assertIn("authorization_endpoint", response.json())
        self.assertEqual(self.client.get("/o/.well-known/jwks.json").status_code, 200)
