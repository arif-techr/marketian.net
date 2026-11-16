from django.test import TestCase
from django.urls import reverse

from tracker.models import Domain, Site
from workspaces.models import Workspace


class CaddyAskTests(TestCase):
    def setUp(self):
        site = Site.objects.create(workspace=Workspace.objects.create(name="A", slug="a"), name="Shop", primary_domain="shop.com")
        for hostname, status in [("ok.shop.com", "verified"), ("flaky.shop.com", "failing"), ("new.shop.com", "pending"), ("off.shop.com", "disabled")]:
            Domain.objects.create(site=site, hostname=hostname, status=status)

    def ask(self, domain):
        return self.client.get(reverse("internal:caddy_ask"), {"domain": domain}).status_code

    def test_only_serving_domains_get_certificates(self):
        self.assertEqual(self.ask("ok.shop.com"), 200)
        self.assertEqual(self.ask("OK.shop.com."), 200)
        self.assertEqual(self.ask("flaky.shop.com"), 200)
        for domain in ["new.shop.com", "off.shop.com", "random.example.com", ""]:
            self.assertEqual(self.ask(domain), 404, domain)

    def test_healthz(self):
        response = self.client.get(reverse("internal:healthz"))
        self.assertEqual(response.json(), {"ok": True})
