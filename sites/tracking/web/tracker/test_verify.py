from types import SimpleNamespace

import dns.resolver
from django.test import TestCase, override_settings

from workspaces.models import Workspace

from .models import Domain, Site
from .verify import FAILS_BEFORE_FAILING, verify_domain


class FakeResolver:
    def __init__(self, cname=None, a=()):
        self.records = {"CNAME": [cname] if cname else [], "A": list(a)}

    def resolve(self, hostname, record):
        answers = self.records[record]
        if not answers:
            raise dns.resolver.NoAnswer()
        return [SimpleNamespace(target=value + ".") if record == "CNAME" else value for value in answers]


@override_settings(DOMAIN_VERIFY_MODE="dns", EDGE_CNAME_TARGET="edge.marketian.net", EDGE_PUBLIC_IP="203.0.113.10")
class VerifyTests(TestCase):
    def setUp(self):
        self.site = Site.objects.create(workspace=Workspace.objects.create(name="A", slug="a"), name="Shop", primary_domain="shop.com")
        self.domain = Domain.objects.create(site=self.site, hostname="data.shop.com")

    def test_right_cname_verifies(self):
        result = verify_domain(self.domain, FakeResolver(cname="Edge.Marketian.net"))
        self.assertTrue(result.ok)
        self.domain.refresh_from_db()
        self.assertEqual(self.domain.status, Domain.VERIFIED)
        self.assertIsNotNone(self.domain.verified_at)
        self.assertEqual(self.domain.dns_seen["cname"], "edge.marketian.net")

    def test_a_record_to_our_ip_verifies(self):
        self.assertTrue(verify_domain(self.domain, FakeResolver(a=["203.0.113.10"])).ok)

    def test_wrong_target_explains_what_to_fix(self):
        result = verify_domain(self.domain, FakeResolver(cname="shops.myshopify.com"))
        self.assertFalse(result.ok)
        self.assertIn("shops.myshopify.com", result.message)
        self.assertEqual(Domain.objects.get().status, Domain.PENDING)

    def test_cloudflare_proxy_gets_a_hint(self):
        result = verify_domain(self.domain, FakeResolver(a=["104.21.1.1"]))
        self.assertIn("grey cloud", result.message)

    def test_missing_record(self):
        self.assertIn("No DNS record", verify_domain(self.domain, FakeResolver()).message)

    def test_verified_domain_turns_failing_after_repeated_failures(self):
        verify_domain(self.domain, FakeResolver(cname="edge.marketian.net"))
        for _ in range(FAILS_BEFORE_FAILING - 1):
            verify_domain(self.domain, FakeResolver())
        self.assertEqual(self.domain.status, Domain.VERIFIED)
        verify_domain(self.domain, FakeResolver())
        self.assertEqual(self.domain.status, Domain.FAILING)
        verify_domain(self.domain, FakeResolver(cname="edge.marketian.net"))
        self.assertEqual((self.domain.status, self.domain.fail_count), (Domain.VERIFIED, 0))

    def test_same_origin_checks_the_token(self):
        domain = Domain.objects.create(site=self.site, hostname="shop.com", mode=Domain.SAME_ORIGIN)
        seen = []
        result = verify_domain(domain, fetch=lambda url: seen.append(url) or domain.verify_token + "\n")
        self.assertTrue(result.ok)
        self.assertEqual(seen, [f"https://shop.com/{self.site.path_prefix}/_v"])
        self.assertFalse(verify_domain(domain, fetch=lambda url: "<html>shop</html>").ok)

    def test_unreachable_same_origin_is_reported(self):
        domain = Domain.objects.create(site=self.site, hostname="shop.com", mode=Domain.SAME_ORIGIN)

        def fail(url):
            raise TimeoutError()

        self.assertIn("TimeoutError", verify_domain(domain, fetch=fail).message)

    @override_settings(DOMAIN_VERIFY_MODE="trust")
    def test_trust_mode_skips_the_check(self):
        self.assertTrue(verify_domain(self.domain, FakeResolver()).ok)
        self.assertEqual(self.domain.status, Domain.VERIFIED)

    def test_disabled_domains_stay_off(self):
        self.domain.status = Domain.DISABLED
        self.domain.save()
        self.assertFalse(verify_domain(self.domain, FakeResolver(cname="edge.marketian.net")).ok)
        self.assertEqual(Domain.objects.get().status, Domain.DISABLED)
