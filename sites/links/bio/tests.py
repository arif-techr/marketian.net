import io
import shutil
import tempfile
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from .models import Event, Item, Page, Subscriber

User = get_user_model()
BROWSER = "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Mobile Safari/537.36"
MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=MEDIA)
class BioPageTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user("jane", "jane@example.com", first_name="Jane", last_name="Doe")
        self.client.force_login(self.user)

    def page(self, **fields):
        return Page.objects.create(owner=self.user, handle="jane", title="Jane Doe", **fields)

    def visitor(self):
        """Someone else looking at the page."""
        self.client.logout()
        return self.client

    # ---- making the page

    def test_new_users_make_their_page_first(self):
        self.assertRedirects(self.client.get(reverse("bio:items")), reverse("bio:create"))
        response = self.client.get(reverse("bio:create"))
        self.assertContains(response, 'value="jane"')  # suggested from the email
        self.client.post(reverse("bio:create"), {"handle": "@Jane.Doe", "title": "Jane"})
        self.assertEqual(Page.objects.get().handle, "jane.doe")

    def test_handle_rules(self):
        Page.objects.create(owner=User.objects.create_user("bob"), handle="taken", title="Bob")
        for handle in ["taken", "a", "-bad", "with space"]:
            with self.subTest(handle=handle):
                self.client.post(reverse("bio:create"), {"handle": handle, "title": "Jane"})
        self.assertFalse(Page.objects.filter(owner=self.user).exists())

    def test_add_items_newest_first_and_reorder(self):
        page = self.page()
        add = reverse("bio:items")
        self.client.post(add, {"kind": "link", "title": "Shop", "url": "https://shop.example", "is_active": "on"})
        self.client.post(add, {"kind": "header", "title": "My work", "url": "https://ignored.example", "is_active": "on"})
        self.client.post(add, {"kind": "video", "title": "Intro", "url": "https://youtu.be/dQw4w9WgXcQ", "is_active": "on"})
        self.assertEqual([i.title for i in page.items.all()], ["Intro", "My work", "Shop"])
        self.assertEqual(page.items.get(title="My work").url, "")
        shop = page.items.get(title="Shop")
        self.client.post(reverse("bio:item_action", args=[shop.pk, "up"]))
        self.assertEqual([i.title for i in page.items.all()], ["Intro", "Shop", "My work"])

    def test_item_checks(self):
        self.page()
        add = reverse("bio:items")
        self.assertContains(self.client.post(add, {"kind": "link", "title": "No url"}), "Add the address")
        self.assertContains(self.client.post(add, {"kind": "video", "title": "Not YouTube", "url": "https://vimeo.com/1"}), "YouTube")
        self.assertContains(self.client.post(add, {"kind": "link", "title": "Bad", "url": "javascript:alert(1)"}), "valid URL")
        self.assertFalse(Item.objects.exists())

    def test_hide_edit_delete(self):
        page = self.page()
        item = page.items.create(title="Shop", url="https://shop.example")
        self.client.post(reverse("bio:item_action", args=[item.pk, "toggle"]))
        item.refresh_from_db()
        self.assertFalse(item.is_active)
        self.client.post(reverse("bio:item_edit", args=[item.pk]), {"kind": "link", "title": "Store", "url": "https://store.example"})
        item.refresh_from_db()
        self.assertEqual(item.title, "Store")
        self.client.post(reverse("bio:item_action", args=[item.pk, "delete"]))
        self.assertFalse(Item.objects.exists())

    def test_others_cannot_touch_my_items(self):
        page = self.page()
        item = page.items.create(title="Shop", url="https://shop.example")
        self.client.force_login(User.objects.create_user("bob"))
        Page.objects.create(owner=User.objects.get(username="bob"), handle="bob", title="Bob")
        self.assertEqual(self.client.post(reverse("bio:item_action", args=[item.pk, "delete"])).status_code, 404)
        self.assertTrue(Item.objects.exists())

    def test_photo_is_made_small_and_square(self):
        page = self.page()
        big = io.BytesIO()
        Image.new("RGB", (1600, 900), "red").save(big, "PNG")
        self.client.post(reverse("bio:appearance"), {
            "profile-title": "Jane", "profile-bio": "Hi", "profile-avatar": SimpleUploadedFile("me.png", big.getvalue(), "image/png"),
            "look-theme": "sunset", "look-button_style": "pill", "look-bg_color": "#ffffff", "look-text_color": "#000000",
            "look-button_color": "#6d5efc", "look-button_text_color": "#ffffff",
        })
        page.refresh_from_db()
        self.assertEqual((page.theme, page.button_style), ("sunset", "pill"))
        with Image.open(page.avatar.path) as photo:
            self.assertEqual((photo.size, photo.format), ((400, 400), "JPEG"))

    def test_not_an_image_is_refused(self):
        self.page()
        response = self.client.post(reverse("bio:appearance"), {
            "profile-title": "Jane", "profile-avatar": SimpleUploadedFile("me.png", b"not an image", "image/png"),
            "look-theme": "light", "look-button_style": "rounded", "look-bg_color": "#ffffff", "look-text_color": "#000000",
            "look-button_color": "#6d5efc", "look-button_text_color": "#ffffff",
        })
        self.assertContains(response, "Upload a valid image")

    # ---- the public page

    def test_public_page_shows_visible_items_and_socials(self):
        page = self.page(bio="Designer", instagram="@jane", whatsapp="8801712345678")
        page.items.create(title="Shop", url="https://shop.example")
        page.items.create(title="Hidden", url="https://hidden.example", is_active=False)
        page.items.create(title="Later", url="https://later.example", show_from=timezone.now() + timedelta(days=1))
        page.items.create(title="Gone", url="https://gone.example", show_until=timezone.now() - timedelta(days=1))
        page.items.create(kind="video", title="Intro", url="https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        response = self.visitor().get("/@jane", HTTP_USER_AGENT=BROWSER)
        self.assertContains(response, "Designer")
        self.assertContains(response, "Shop")
        self.assertContains(response, "youtube-nocookie.com/embed/dQw4w9WgXcQ")
        self.assertContains(response, "https://instagram.com/jane")
        self.assertContains(response, "https://wa.me/8801712345678")
        for hidden in ["Hidden", "Later", "Gone"]:
            self.assertNotContains(response, hidden)

    def test_views_and_clicks_are_counted(self):
        page = self.page()
        shop = page.items.create(title="Shop", url="https://shop.example")
        browser = self.visitor()
        browser.get("/@jane", HTTP_USER_AGENT=BROWSER, HTTP_REFERER="https://l.instagram.com/")
        go = browser.get(f"/@jane/go/{shop.pk}", HTTP_USER_AGENT=BROWSER)
        self.assertEqual(go["Location"], "https://shop.example")
        browser.get("/@jane", HTTP_USER_AGENT="facebookexternalhit/1.1")  # link preview: not counted
        page.refresh_from_db()
        shop.refresh_from_db()
        self.assertEqual((page.views, shop.clicks), (1, 1))
        view = Event.objects.get(kind=Event.VIEW)
        self.assertEqual((view.referrer, view.device, view.browser, view.os), ("l.instagram.com", "Mobile", "Chrome", "Android"))

    def test_owner_and_preview_are_not_counted(self):
        page = self.page()
        self.client.get("/@jane", HTTP_USER_AGENT=BROWSER)
        preview = self.client.get("/@jane?preview=1", HTTP_USER_AGENT=BROWSER)
        self.assertEqual(preview["X-Frame-Options"], "SAMEORIGIN")
        page.refresh_from_db()
        self.assertEqual(page.views, 0)

    def test_unpublished_and_missing_pages(self):
        self.page(is_published=False)
        self.assertContains(self.client.get("/@jane?preview=1"), "Jane Doe")  # the owner still sees the preview
        browser = self.visitor()
        self.assertEqual(browser.get("/@jane").status_code, 404)
        self.assertEqual(browser.get("/@nobody").status_code, 404)

    def test_hidden_item_link_goes_back_to_the_page(self):
        page = self.page()
        item = page.items.create(title="Hidden", url="https://hidden.example", is_active=False)
        self.assertRedirects(self.visitor().get(f"/@jane/go/{item.pk}"), "/@jane", fetch_redirect_response=False)

    def test_sensitive_warning(self):
        self.page(sensitive=True)
        page = self.page_html = self.visitor().get("/@jane")
        self.assertContains(page, "Sensitive content")
        self.assertNotContains(self.client.get("/@jane?continue=1"), "Sensitive content")

    def test_email_signups(self):
        page = self.page(collect_emails=True)
        browser = self.visitor()
        response = browser.post("/@jane/subscribe/", {"email": "Fan@Example.com"}, HTTP_USER_AGENT=BROWSER)
        self.assertRedirects(response, "/@jane?subscribed=1#signup", fetch_redirect_response=False)
        browser.post("/@jane/subscribe/", {"email": "fan@example.com"}, HTTP_USER_AGENT=BROWSER)  # twice: kept once
        browser.post("/@jane/subscribe/", {"email": "bot@example.com", "website": "spam"}, HTTP_USER_AGENT=BROWSER)
        self.assertEqual(list(Subscriber.objects.values_list("email", flat=True)), ["fan@example.com"])
        self.client.force_login(self.user)
        csv = self.client.get(reverse("bio:subscribers"), {"format": "csv"}).content.decode()
        self.assertIn("fan@example.com", csv)
        self.assertEqual(page.subscribers.count(), 1)

    def test_signups_off_means_no_form(self):
        self.page()
        self.assertEqual(self.visitor().post("/@jane/subscribe/", {"email": "fan@example.com"}).status_code, 404)

    def test_stats_and_qr(self):
        page = self.page()
        page.items.create(title="Shop", url="https://shop.example")
        self.assertContains(self.client.get(reverse("bio:stats")), "Clicks per button")
        self.assertTrue(self.client.get(reverse("bio:qr", args=["png"])).content.startswith(b"\x89PNG"))

    def test_youtube_addresses(self):
        for url in ["https://youtu.be/dQw4w9WgXcQ", "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=10",
                    "https://m.youtube.com/shorts/dQw4w9WgXcQ", "https://www.youtube.com/embed/dQw4w9WgXcQ"]:
            with self.subTest(url=url):
                self.assertEqual(Item(url=url).youtube_id, "dQw4w9WgXcQ")
        self.assertEqual(Item(url="https://evil.example/watch?v=dQw4w9WgXcQ").youtube_id, "")
