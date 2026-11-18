from io import StringIO

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import ContactMessage, Project, Tool

User = get_user_model()


@override_settings(CONTACT_RECIPIENTS=["owner@marketian.net"])
class SiteTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", stdout=StringIO())

    def setUp(self):
        cache.clear()

    def test_pages_render(self):
        for name in ["home", "about", "services", "tools", "portfolio", "contact"]:
            with self.subTest(page=name):
                self.assertEqual(self.client.get(reverse(f"core:{name}")).status_code, 200)

    def test_project_detail_and_filter(self):
        project = Project.objects.first()
        self.assertContains(self.client.get(project.get_absolute_url()), project.title)
        response = self.client.get(reverse("core:portfolio"), {"category": "SEO"})
        self.assertTrue(all(p.category == "SEO" for p in response.context["projects"]))

    def test_seo_endpoints_and_404(self):
        self.assertContains(self.client.get("/robots.txt"), "Sitemap:")
        self.assertContains(self.client.get("/sitemap.xml"), "/portfolio/")
        self.assertEqual(self.client.get("/does-not-exist/").status_code, 404)

    def _post(self, **overrides):
        data = {"name": "Jane Doe", "email": "jane@example.com", "subject": "New website",
                "message": "I would like a new website for my shop.", "budget": "", "phone": "", "website": ""}
        data.update(overrides)
        return self.client.post(reverse("core:contact"), data, follow=True)

    def test_contact_saves_and_emails(self):
        response = self._post()
        self.assertContains(response, "Your message has been sent")
        msg = ContactMessage.objects.get()
        self.assertTrue(msg.email_sent)
        self.assertEqual(len(mail.outbox), 2)  # notification to me + auto-reply to the visitor
        self.assertEqual(mail.outbox[0].to, ["owner@marketian.net"])
        self.assertEqual(mail.outbox[0].reply_to, ["jane@example.com"])
        self.assertEqual(mail.outbox[1].to, ["jane@example.com"])

    def test_contact_validation(self):
        response = self._post(email="not-an-email", message="hi")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ContactMessage.objects.exists())
        self.assertTrue(response.context["form"].errors)

    def test_honeypot_blocks_bots(self):
        self._post(website="http://spam.example")
        self.assertFalse(ContactMessage.objects.exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_rate_limit(self):
        for _ in range(6):
            self._post()
        self.assertEqual(ContactMessage.objects.count(), 5)

    @override_settings(CANONICAL_HOST="marketian.net", ALLOWED_HOSTS=["marketian.net", "marketain.net"])
    def test_alias_domain_redirects(self):
        response = self.client.get("/about/", HTTP_HOST="marketain.net")
        self.assertEqual(response.status_code, 301)
        self.assertTrue(response["Location"].endswith("marketian.net/about/"))

    def test_pages_load_without_full_reload(self):
        response = self.client.get(reverse("core:home"))
        self.assertContains(response, 'hx-boost="true"')
        self.assertContains(response, "js/vendor/htmx-2.0.4.min.js")

    def test_hover_prefetch_is_kept_briefly(self):
        preloaded = self.client.get(reverse("core:about"), HTTP_HX_PRELOADED="true")
        self.assertIn("max-age=10", preloaded["Cache-Control"])
        self.assertIn("private", preloaded["Cache-Control"])
        self.assertFalse(self.client.get(reverse("core:about")).has_header("Cache-Control"))

    def test_hover_prefetch_never_keeps_a_one_time_notice(self):
        data = {"name": "Jane Doe", "email": "jane@example.com", "subject": "Hi", "message": "A new website please."}
        self.client.post(reverse("core:contact"), data)  # leaves "message sent" waiting for the next page
        response = self.client.get(reverse("core:contact"), HTTP_HX_PRELOADED="true")
        self.assertContains(response, "Your message has been sent")
        self.assertFalse(response.has_header("Cache-Control"))

    def test_marketing_tools_button_in_menu(self):
        response = self.client.get(reverse("core:home"))
        self.assertContains(response, f'class="nav-tools" href="{reverse("core:tools")}"')
        self.assertContains(response, "Tools I build for marketers")

    def test_tools_page_lists_active_tools(self):
        Tool.objects.create(name="Hidden tool", tagline="x", url="https://hidden.marketian.net", is_active=False)
        response = self.client.get(reverse("core:tools"))
        self.assertContains(response, 'href="https://wa.marketian.net"')
        self.assertContains(response, "Invite only")
        self.assertNotContains(response, "Hidden tool")

    def test_coming_soon_tool_has_no_open_button(self):
        response = self.client.get(reverse("core:tools"))
        self.assertNotContains(response, 'href="https://metadata.marketian.net"')
        self.assertContains(response, "Get notified")
        self.assertIn(reverse("core:tools"), self.client.get("/sitemap.xml").content.decode())


@override_settings(ADMIN_EMAILS={"owner@marketian.net"})
class AdminSignInTests(TestCase):
    """The admin pages use the Marketian account: no admin password, staff only from ADMIN_EMAILS."""

    def sign_in(self, email, verified=True):
        from types import SimpleNamespace

        from allauth.account.signals import user_logged_in

        user = User.objects.get_or_create(username=email, defaults={"email": email})[0]
        self.client.force_login(user)
        # A Marketian sign-in: the claims are what accounts.marketian.net sent.
        login = SimpleNamespace(account=SimpleNamespace(extra_data={"userinfo": {"email": email, "email_verified": verified}}))
        user_logged_in.send(sender=User, request=None, user=user, sociallogin=login)
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

    def test_listed_but_unverified_email_gets_no_access(self):
        # Anyone can sign up on accounts with an admin's address; only a verified one counts.
        user = self.sign_in("owner@marketian.net", verified=False)
        self.assertFalse(user.is_staff or user.is_superuser)
        self.assertContains(self.client.get(reverse("admin:login")), "has no admin access", status_code=403)

    def test_removing_an_email_takes_access_away_at_next_sign_in(self):
        self.sign_in("owner@marketian.net")
        with self.settings(ADMIN_EMAILS=set()):
            user = self.sign_in("owner@marketian.net")
        self.assertFalse(user.is_staff or user.is_superuser)

    def test_outside_next_is_ignored(self):
        self.sign_in("owner@marketian.net")
        response = self.client.get(reverse("admin:login"), {"next": "https://evil.example/"})
        self.assertRedirects(response, "/admin/", fetch_redirect_response=False)

    def test_only_admin_emails_can_get_an_account_here(self):
        from types import SimpleNamespace

        from .admin_signin import SignupOnlyForAdmins

        adapter = SignupOnlyForAdmins()
        def login(email, verified=True):
            claims = {"email": email, "email_verified": verified}
            return SimpleNamespace(user=SimpleNamespace(email=email), account=SimpleNamespace(extra_data={"id_token": claims}))

        self.assertTrue(adapter.is_open_for_signup(None, login("owner@marketian.net")))
        self.assertFalse(adapter.is_open_for_signup(None, login("owner@marketian.net", verified=False)))
        self.assertFalse(adapter.is_open_for_signup(None, login("visitor@example.com")))
