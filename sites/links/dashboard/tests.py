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


@override_settings(ADMIN_EMAILS={"owner@marketian.net"})
class AdminSignInTests(TestCase):
    """The admin pages use the Marketian account: no admin password, staff only from ADMIN_EMAILS."""

    def sign_in(self, email):
        from allauth.account.signals import user_logged_in

        user = User.objects.get_or_create(username=email, defaults={"email": email})[0]
        self.client.force_login(user)
        user_logged_in.send(sender=User, request=None, user=user, sociallogin=object())  # a Marketian sign-in
        user.refresh_from_db()
        return user

    def test_signed_out_admins_get_the_marketian_button_not_a_password_form(self):
        response = self.client.get(reverse("admin:login"), {"next": "/admin/"})
        self.assertContains(response, "/accounts/oidc/marketian/login/")
        self.assertContains(response, "Continue with Marketian account")
        self.assertNotContains(response, 'name="password"')
        self.assertEqual(self.client.get("/admin/").status_code, 302)

    def test_listed_email_becomes_staff_and_gets_in(self):
        user = self.sign_in("Owner@Marketian.net")
        self.assertTrue(user.is_staff and user.is_superuser)
        self.assertEqual(self.client.get("/admin/").status_code, 200)
        self.assertRedirects(self.client.get(reverse("admin:login"), {"next": "/admin/"}), "/admin/", fetch_redirect_response=False)

    def test_other_accounts_are_refused(self):
        user = self.sign_in("someone@example.com")
        self.assertFalse(user.is_staff)
        response = self.client.get(reverse("admin:login"), {"next": "/admin/"})
        self.assertContains(response, "has no admin access", status_code=403)

    def test_removing_an_email_takes_access_away_at_next_sign_in(self):
        self.sign_in("owner@marketian.net")
        with self.settings(ADMIN_EMAILS=set()):
            user = self.sign_in("owner@marketian.net")
        self.assertFalse(user.is_staff or user.is_superuser)

    def test_outside_next_is_ignored(self):
        self.sign_in("owner@marketian.net")
        response = self.client.get(reverse("admin:login"), {"next": "https://evil.example/"})
        self.assertRedirects(response, "/admin/", fetch_redirect_response=False)
