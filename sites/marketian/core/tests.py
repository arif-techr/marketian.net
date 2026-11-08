from io import StringIO

from django.core import mail
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import ContactMessage, Project, Tool


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
