from allauth.socialaccount.models import SocialAccount
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

User = get_user_model()


@override_settings(ACCOUNTS_URL="https://accounts.marketian.net")
class DashboardTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("jane", "jane@example.com")
        # Stored the way allauth stores an OpenID Connect sign-in.
        SocialAccount.objects.create(
            user=self.user, provider="marketian", uid="42",
            extra_data={"id_token": {"sub": "42"}, "userinfo": {"name": "Jane Doe", "picture": "https://avatars.example/jane.png"}},
        )

    def test_landing_renders(self):
        response = self.client.get(reverse("dashboard:landing"))
        self.assertContains(response, reverse("dashboard:login"))
        self.assertContains(response, 'hx-boost="true"')

    def test_dashboard_needs_sign_in(self):
        response = self.client.get(reverse("dashboard:app"))
        self.assertRedirects(response, f"{reverse('dashboard:login')}?next={reverse('dashboard:app')}", fetch_redirect_response=False)

    def test_sign_in_goes_to_the_marketian_account(self):
        response = self.client.get(reverse("dashboard:login"))
        self.assertContains(response, "/accounts/oidc/marketian/login/")
        # Leaves for accounts.marketian.net, so it must be a real page load.
        self.assertContains(response, 'method="post" hx-boost="false"')

    def test_sign_in_ignores_outside_next(self):
        response = self.client.get(reverse("dashboard:login"), {"next": "https://evil.example/"})
        self.assertEqual(response.context["next"], "")
        response = self.client.get(reverse("dashboard:login"), {"next": "/app/"})
        self.assertEqual(response.context["next"], "/app/")

    def test_signed_in_people_skip_the_sign_in_page(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("dashboard:login"))
        self.assertRedirects(response, reverse("dashboard:app"), fetch_redirect_response=False)

    def test_dashboard_shows_the_account(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("dashboard:app"))
        self.assertContains(response, "Welcome, Jane Doe")
        self.assertContains(response, "https://avatars.example/jane.png")
        self.assertContains(response, 'hx-history="false"')  # private page: no copy in browser storage

    def test_sign_out_also_signs_out_of_the_account(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("dashboard:logout"))
        self.assertTrue(response["Location"].startswith("https://accounts.marketian.net/accounts/logout/?next="))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_hover_prefetch_is_kept_briefly(self):
        preloaded = self.client.get(reverse("dashboard:landing"), HTTP_HX_PRELOADED="true")
        self.assertIn("max-age=10", preloaded["Cache-Control"])
        self.assertIn("private", preloaded["Cache-Control"])
        self.assertFalse(self.client.get(reverse("dashboard:landing")).has_header("Cache-Control"))
