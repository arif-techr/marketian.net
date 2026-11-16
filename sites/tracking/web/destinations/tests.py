from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase, override_settings

from tracker.models import Site
from workspaces.models import Workspace

from . import registry
from .models import Destination

META = {"pixel_id": "123456789012345"}
TOKEN = {"access_token": "EAAB" + "x" * 40 + "9z8y"}


class DestinationTests(TestCase):
    def setUp(self):
        self.site = Site.objects.create(workspace=Workspace.objects.create(name="A", slug="a"), name="Shop", primary_domain="shop.com")

    def make(self, type="meta", config=META, secret=TOKEN, **kwargs):
        destination = Destination(site=self.site, type=type, config=config, **kwargs)
        destination.full_clean()
        destination.set_secret(secret)
        destination.save()
        return destination

    def test_secret_is_stored_encrypted_and_only_its_hint_is_shown(self):
        destination = Destination.objects.get(pk=self.make().pk)
        self.assertNotIn(TOKEN["access_token"], destination.secret_enc)
        self.assertTrue(destination.secret_enc.startswith("v1:"))
        self.assertEqual(destination.masked_secret, "••••9z8y")
        self.assertEqual(destination.get_secret(), TOKEN)
        self.assertNotIn(TOKEN["access_token"], str(destination))

    def test_defaults_are_applied(self):
        destination = self.make()
        self.assertEqual(destination.consent_required, ["ad_storage", "ad_user_data"])
        events = destination.effective_event_map()
        self.assertEqual((events["Purchase"], events["Refund"]), ("Purchase", None))
        ga4 = self.make("ga4", {"measurement_id": "G-AB12CD34EF"}, {"api_secret": "abcDEF123456"})
        self.assertEqual(ga4.consent_required, ["analytics_storage"])
        self.assertEqual(ga4.effective_event_map()["Purchase"], "purchase")

    def test_overrides_win_over_defaults(self):
        destination = self.make(event_map={"PageView": None, "Subscribe": "Subscribe"})
        events = destination.effective_event_map()
        self.assertIsNone(events["PageView"])
        self.assertEqual(events["Subscribe"], "Subscribe")
        self.assertEqual(events["Purchase"], "Purchase")

    def test_chosen_consent_is_kept_even_when_empty(self):
        self.assertEqual(self.make(consent_required=[]).consent_required, [])

    def test_config_is_checked_per_type(self):
        cases = [
            ("meta", {"pixel_id": "abc"}),
            ("meta", {}),
            ("ga4", {"measurement_id": "UA-1234"}),
            ("tiktok", {"pixel_code": "lower case"}),
            ("webhook", {"url": "ftp://example.com"}),
            ("nope", {}),
        ]
        for type, config in cases:
            with self.assertRaises(ValidationError, msg=(type, config)):
                Destination(site=self.site, type=type, config=config).full_clean()

    def test_unknown_config_keys_are_dropped_and_lists_split(self):
        destination = self.make("webhook", {"url": "https://hooks.shop.com/mt", "events": "Purchase, Lead", "junk": 1}, {"signing_secret": "s" * 20})
        self.assertEqual(destination.config, {"url": "https://hooks.shop.com/mt", "events": ["Purchase", "Lead"]})

    @override_settings(DEBUG=False)
    def test_webhooks_need_https_in_production(self):
        with self.assertRaises(ValidationError):
            Destination(site=self.site, type="webhook", config={"url": "http://hooks.shop.com"}).full_clean()

    def test_bad_secret_or_event_names_are_refused(self):
        with self.assertRaises(ValidationError):
            Destination(site=self.site, type="meta", config=META).set_secret({"access_token": "short"})
        with self.assertRaises(ValidationError):
            Destination(site=self.site, type="meta", config=META, event_map={"Purchase": "has space"}).full_clean()
        with self.assertRaises(ValidationError):
            Destination(site=self.site, type="meta", config=META, consent_required=["cookies"]).full_clean()

    def test_labels_are_unique_per_site_and_type(self):
        self.make()
        with self.assertRaises(ValidationError):  # the form's check
            self.make()
        with self.assertRaises(IntegrityError):  # and the database's
            Destination.objects.create(site=self.site, type="meta", label="Main", config=META)

    def test_every_type_maps_every_standard_event(self):
        for kind in registry.TYPES.values():
            self.assertEqual(set(kind.default_event_map), set(registry.STANDARD_EVENTS), kind.key)
            self.assertTrue(kind.secret_fields, kind.key)
