from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

User = get_user_model()


@override_settings(ACCOUNTS_URL="https://accounts.marketian.net")
class SignInTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("jane", "jane@example.com")

    def test_landing_renders(self):
        response = self.client.get(reverse("dashboard:landing"))
        self.assertContains(response, reverse("dashboard:login"))
        self.assertContains(response, 'hx-boost="true"')

    def test_app_needs_sign_in(self):
        response = self.client.get(reverse("shortener:links"))
        self.assertRedirects(response, f"{reverse('dashboard:login')}?next={reverse('shortener:links')}", fetch_redirect_response=False)

    def test_sign_in_goes_to_the_marketian_account(self):
        response = self.client.get(reverse("dashboard:login"))
        self.assertContains(response, "/accounts/oidc/marketian/login/")
        self.assertContains(response, 'method="post" hx-boost="false"')

    def test_sign_in_ignores_outside_next(self):
        response = self.client.get(reverse("dashboard:login"), {"next": "https://evil.example/"})
        self.assertEqual(response.context["next"], "")

    def test_signed_in_people_go_to_their_links(self):
        self.client.force_login(self.user)
        self.assertRedirects(self.client.get(reverse("dashboard:login")), reverse("shortener:links"), fetch_redirect_response=False)

    def test_sign_out_also_signs_out_of_the_account(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("dashboard:logout"))
        self.assertTrue(response["Location"].startswith("https://accounts.marketian.net/accounts/logout/?next="))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_hover_prefetch_is_kept_briefly(self):
        preloaded = self.client.get(reverse("dashboard:landing"), HTTP_HX_PRELOADED="true")
        self.assertIn("max-age=10", preloaded["Cache-Control"])
