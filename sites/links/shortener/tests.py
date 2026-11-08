from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .forms import add_utm
from .models import Click, Link

User = get_user_model()
BROWSER = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"


class ShortLinkTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user("jane", "jane@example.com")
        self.client.force_login(self.user)

    def make(self, **data):
        return self.client.post(reverse("shortener:links"), {"destination": "https://example.com/page", **data})

    def visit(self, slug, ua=BROWSER, **extra):
        return self.client.get(f"/{slug}", HTTP_USER_AGENT=ua, **extra)

    # ---- making links

    def test_shorten_with_a_random_name(self):
        response = self.make()
        link = Link.objects.get()
        self.assertRedirects(response, reverse("shortener:detail", args=[link.pk]))
        self.assertEqual(link.owner, self.user)
        self.assertEqual(len(link.slug), 6)
        self.assertNotRegex(link.slug, r"[l1o0]")

    def test_custom_name_is_lowercased(self):
        self.make(slug="Summer-Sale")
        self.assertTrue(Link.objects.filter(slug="summer-sale").exists())

    def test_custom_name_rules(self):
        Link.objects.create(owner=self.user, slug="taken", destination="https://example.com")
        for slug, error in [("taken", "taken"), ("admin", "reserved"), ("a b", "letters"), ("-x", "letters")]:
            with self.subTest(slug=slug):
                self.assertContains(self.make(slug=slug), error)
        self.assertEqual(Link.objects.count(), 1)

    def test_only_web_addresses(self):
        for url in ["javascript:alert(1)", "ftp://example.com/file", "not a url"]:
            with self.subTest(url=url):
                self.make(destination=url)
        self.assertFalse(Link.objects.exists())

    @override_settings(ALLOWED_HOSTS=["links.marketian.net"])
    def test_no_links_to_the_shortener_itself(self):
        response = self.client.post(reverse("shortener:links"), {"destination": "https://links.marketian.net/abc"},
                                    HTTP_HOST="links.marketian.net")
        self.assertContains(response, "already a short link")

    def test_address_without_https_gets_it(self):
        self.make(destination="example.com/page")
        self.assertEqual(Link.objects.get().destination, "https://example.com/page")

    def test_utm_tags_are_added(self):
        self.make(destination="https://example.com/?a=1&utm_source=old", utm_source="facebook", utm_campaign="sale")
        self.assertEqual(Link.objects.get().destination, "https://example.com/?a=1&utm_source=facebook&utm_campaign=sale")
        self.assertEqual(add_utm("https://x.com/", {"utm_source": ""}), "https://x.com/")

    @override_settings(LINKS_PER_DAY=2)
    def test_daily_limit(self):
        self.make()
        self.make()
        self.assertContains(self.make(), "the most for one day")
        self.assertEqual(Link.objects.count(), 2)

    # ---- following links

    def test_redirect_counts_the_click(self):
        link = Link.objects.create(owner=self.user, slug="sale", destination="https://example.com/sale")
        self.client.logout()
        response = self.visit("Sale", HTTP_REFERER="https://www.facebook.com/some/post")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "https://example.com/sale")
        self.assertIn("no-store", response["Cache-Control"])
        click = Click.objects.get()
        self.assertEqual((click.referrer, click.device, click.browser, click.os), ("facebook.com", "Mobile", "Safari", "iOS"))
        link.refresh_from_db()
        self.assertEqual(link.clicks, 1)

    def test_bots_and_prefetch_are_sent_on_but_not_counted(self):
        Link.objects.create(owner=self.user, slug="sale", destination="https://example.com/sale")
        for ua, extra in [("WhatsApp/2.23.20.0", {}), ("facebookexternalhit/1.1", {}), ("", {}), (BROWSER, {"HTTP_HX_PRELOADED": "true"})]:
            with self.subTest(ua=ua):
                self.assertEqual(self.visit("sale", ua, **extra).status_code, 302)
        self.assertFalse(Click.objects.exists())

    def test_unique_visitors(self):
        Link.objects.create(owner=self.user, slug="sale", destination="https://example.com/sale")
        self.visit("sale")
        self.visit("sale")
        self.visit("sale", ua=BROWSER.replace("iPhone", "iPad"))
        self.assertEqual(Click.objects.count(), 3)
        self.assertEqual(Click.objects.values("visitor").distinct().count(), 2)

    def test_missing_off_and_expired_links(self):
        Link.objects.create(owner=self.user, slug="off", destination="https://example.com", is_active=False)
        Link.objects.create(owner=self.user, slug="old", destination="https://example.com",
                            expires_at=timezone.now() - timedelta(minutes=1))
        self.assertContains(self.visit("nope"), "This link doesn", status_code=404)
        self.assertContains(self.visit("off"), "turned off", status_code=410)
        self.assertContains(self.visit("old"), "expired", status_code=410)
        self.assertFalse(Click.objects.exists())

    def test_password_link(self):
        link = Link(owner=self.user, slug="secret", destination="https://example.com/secret")
        link.set_password("open-sesame")
        link.save()
        self.assertContains(self.visit("secret"), "needs a password")
        wrong = self.client.post("/secret", {"password": "nope"}, HTTP_USER_AGENT=BROWSER)
        self.assertContains(wrong, "That password is wrong")
        right = self.client.post("/secret", {"password": "open-sesame"}, HTTP_USER_AGENT=BROWSER)
        self.assertEqual(right["Location"], "https://example.com/secret")
        self.assertEqual(Click.objects.count(), 1)

    def test_password_guessing_is_limited(self):
        link = Link(owner=self.user, slug="secret", destination="https://example.com/secret")
        link.set_password("open-sesame")
        link.save()
        for _ in range(10):
            self.client.post("/secret", {"password": "nope"}, HTTP_USER_AGENT=BROWSER)
        blocked = self.client.post("/secret", {"password": "open-sesame"}, HTTP_USER_AGENT=BROWSER)
        self.assertContains(blocked, "Too many wrong passwords")

    def test_preview_shows_where_it_goes(self):
        Link.objects.create(owner=self.user, slug="sale", destination="https://example.com/sale")
        self.assertContains(self.client.get("/sale+"), "https://example.com/sale")
        self.assertFalse(Click.objects.exists())

    def test_app_paths_without_slash(self):
        self.assertRedirects(self.client.get("/app"), "/app/", fetch_redirect_response=False)

    # ---- managing links

    def test_list_search_and_detail(self):
        Link.objects.create(owner=self.user, slug="sale", destination="https://example.com/sale", title="Summer sale")
        Link.objects.create(owner=self.user, slug="blog", destination="https://example.com/blog")
        response = self.client.get(reverse("shortener:links"), {"q": "summer"})
        self.assertContains(response, "Summer sale")
        self.assertNotContains(response, "/blog")
        link = Link.objects.get(slug="sale")
        self.assertContains(self.client.get(reverse("shortener:detail", args=[link.pk])), "Last 30 days")

    def test_other_peoples_links_are_hidden(self):
        bob = User.objects.create_user("bob", "bob@example.com")
        link = Link.objects.create(owner=bob, slug="bob", destination="https://example.com")
        self.assertEqual(self.client.get(reverse("shortener:detail", args=[link.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("shortener:delete", args=[link.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("shortener:qr", args=[link.pk, "png"])).status_code, 404)
        self.assertNotContains(self.client.get(reverse("shortener:links")), "/bob")

    def test_edit_turn_off_and_password(self):
        link = Link.objects.create(owner=self.user, slug="sale", destination="https://example.com/sale")
        url = reverse("shortener:detail", args=[link.pk])
        self.client.post(url, {"destination": "https://example.com/new", "slug": "", "title": "", "new_password": "pw-123"})
        link.refresh_from_db()
        self.assertEqual((link.destination, link.slug, link.is_active), ("https://example.com/new", "sale", False))
        self.assertTrue(link.check_password("pw-123"))
        self.client.post(url, {"destination": "https://example.com/new", "slug": "sale", "is_active": "on", "remove_password": "on"})
        link.refresh_from_db()
        self.assertTrue(link.is_active)
        self.assertFalse(link.has_password)

    def test_delete(self):
        link = Link.objects.create(owner=self.user, slug="sale", destination="https://example.com/sale")
        self.client.post(reverse("shortener:delete", args=[link.pk]))
        self.assertFalse(Link.objects.exists())

    def test_qr_codes(self):
        link = Link.objects.create(owner=self.user, slug="sale", destination="https://example.com/sale")
        png = self.client.get(reverse("shortener:qr", args=[link.pk, "png"]), {"download": 1})
        self.assertEqual(png["Content-Type"], "image/png")
        self.assertTrue(png.content.startswith(b"\x89PNG"))
        self.assertIn('filename="sale-qr.png"', png["Content-Disposition"])
        svg = self.client.get(reverse("shortener:qr", args=[link.pk, "svg"]))
        self.assertTrue(svg.content.startswith(b"<svg"))

    def test_csv_export(self):
        Link.objects.create(owner=self.user, slug="sale", destination="https://example.com/sale")
        csv = self.client.get(reverse("shortener:export")).content.decode()
        self.assertIn("http://testserver/sale,https://example.com/sale", csv)
