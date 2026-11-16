import hashlib

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import SimpleTestCase, TestCase

from workspaces.models import Workspace

from .models import ApiKey, Domain, Site, has_blocked_word, new_loader_name, normalise_hostname, safe_random_name


class RandomNameTests(SimpleTestCase):
    def test_names_avoid_block_list_words(self):
        for _ in range(500):
            name = safe_random_name(5)
            self.assertRegex(name, r"^[a-z][a-z0-9]{4}$")
            self.assertFalse(has_blocked_word(name))
        self.assertRegex(new_loader_name(), r"^[a-z][a-z0-9]{2}\.js$")

    def test_blocked_words_are_found_anywhere(self):
        for text in ["track", "x9gtm", "pixel", "QADS1", "fbq"]:
            self.assertTrue(has_blocked_word(text), text)
        self.assertFalse(has_blocked_word("q8r"))

    def test_hostnames_are_normalised(self):
        self.assertEqual(normalise_hostname(" https://Shop.COM/cart?x=1 "), "shop.com")
        self.assertEqual(normalise_hostname("data.shop.com."), "data.shop.com")
        for bad in ["", "shop", "shop.com:8080", "-bad.com", "sh op.com", "http://"]:
            with self.assertRaises(ValidationError, msg=bad):
                normalise_hostname(bad)


class SiteTests(TestCase):
    def setUp(self):
        self.workspace = Workspace.objects.create(name="Agency", slug="agency")

    def make_site(self, **kwargs):
        defaults = {"workspace": self.workspace, "name": "Shop", "primary_domain": "shop.com"}
        return Site.objects.create(**defaults | kwargs)

    def test_new_sites_get_keys_and_a_prefix(self):
        site = self.make_site()
        self.assertRegex(site.public_key, r"^mt_pk_[0-9A-Za-z]{18}$")
        self.assertRegex(site.path_prefix, r"^[a-z][a-z0-9]{3,5}$")
        self.assertFalse(has_blocked_word(site.path_prefix))
        self.assertTrue(site.loader_name.endswith(".js"))
        self.assertNotEqual(site.path_prefix, self.make_site(name="Second").path_prefix)

    def test_site_names_are_unique_per_workspace(self):
        self.make_site()
        Site.objects.create(workspace=Workspace.objects.create(name="Other", slug="other"), name="Shop", primary_domain="shop.com")
        with self.assertRaises(IntegrityError):
            self.make_site()

    def test_clean_normalises_domain_and_currency(self):
        site = Site(workspace=self.workspace, name="Shop", primary_domain="https://Shop.com/", default_currency="usd")
        site.full_clean()
        self.assertEqual((site.primary_domain, site.default_currency), ("shop.com", "USD"))
        with self.assertRaises(ValidationError):
            Site(workspace=self.workspace, name="X", primary_domain="shop.com", default_currency="TAKA").full_clean()

    def test_domain_must_sit_under_the_primary_domain(self):
        site = self.make_site()
        Domain(site=site, hostname="Data.Shop.com").full_clean()
        for bad in ["data.othershop.com", "data.notshop.com", "shop.com.evil.com"]:
            with self.assertRaises(ValidationError, msg=bad):
                Domain(site=site, hostname=bad).full_clean()

    def test_subdomain_mode_needs_a_subdomain(self):
        site = self.make_site()
        with self.assertRaises(ValidationError):
            Domain(site=site, hostname="shop.com", mode=Domain.SUBDOMAIN).full_clean()
        Domain(site=site, hostname="shop.com", mode=Domain.SAME_ORIGIN).full_clean()

    def test_only_verified_or_failing_domains_serve_events(self):
        site = self.make_site()
        served = {status: Domain(site=site, hostname="data.shop.com", status=status).serves_events for status, _ in Domain.STATUSES}
        self.assertEqual(served, {"pending": False, "verified": True, "failing": True, "disabled": False})


class ApiKeyTests(TestCase):
    def test_only_the_hash_is_stored(self):
        site = Site.objects.create(workspace=Workspace.objects.create(name="A", slug="a"), name="Shop", primary_domain="shop.com")
        api_key, full_key = ApiKey.issue(site, "Backend")
        self.assertRegex(full_key, r"^mtk_[0-9A-Za-z]{6}_[0-9A-Za-z]{32}$")
        self.assertTrue(full_key.startswith(api_key.prefix + "_"))
        self.assertEqual(api_key.key_hash, hashlib.sha256(full_key.encode()).hexdigest())
        stored = ApiKey.objects.filter(pk=api_key.pk).values().get()
        self.assertFalse(any(full_key in str(value) for value in stored.values()))
        self.assertTrue(api_key.is_active)
