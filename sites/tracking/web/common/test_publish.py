import io
import json
from unittest import mock

from django.core.management import call_command
from django.test import TestCase

from destinations.models import Destination
from tracker.models import ApiKey, Domain, Site
from workspaces.models import Workspace

from . import crypto, publish
from .testing import FakeRedis


class PublishTests(TestCase):
    def setUp(self):
        self.redis = FakeRedis()
        self.site = Site.objects.create(workspace=Workspace.objects.create(name="A", slug="a"), name="Shop", primary_domain="shop.com")
        self.domain = Domain.objects.create(site=self.site, hostname="data.shop.com", status=Domain.VERIFIED)
        Domain.objects.create(site=self.site, hostname="pending.shop.com")
        self.destination = Destination(site=self.site, type="meta", config={"pixel_id": "123456789012345"})
        self.destination.set_secret({"access_token": "EAAB" + "t" * 40})
        self.destination.save()

    def site_json(self):
        return json.loads(self.redis.get(f"cfg:site:{self.site.pk}"))

    def test_site_host_and_destination_keys_are_written(self):
        api_key, full_key = ApiKey.issue(self.site, "Backend")
        publish.publish_site(self.site.pk, self.redis)

        self.assertEqual(self.redis.get("cfg:host:data.shop.com"), str(self.site.pk))
        self.assertIsNone(self.redis.get("cfg:host:pending.shop.com"))  # not verified: no certificate, no traffic
        config = self.site_json()
        self.assertEqual((config["prefix"], config["loader"], config["hosts"]), (self.site.path_prefix, self.site.loader_name, ["data.shop.com"]))
        self.assertEqual(config["api_keys"], {api_key.prefix: api_key.key_hash})
        self.assertEqual(config["destinations"][0]["event_map"]["Purchase"], "Purchase")
        self.assertEqual(self.redis.published, [("cfg:changed", str(self.site.pk))])

        # Secrets never appear in the edge's config, only encrypted in cfg:dest.
        raw_site = self.redis.get(f"cfg:site:{self.site.pk}")
        self.assertNotIn("EAAB", raw_site)
        self.assertNotIn(full_key, raw_site)
        dest = json.loads(crypto.decrypt(self.redis.get(f"cfg:dest:{self.destination.pk}")))
        self.assertEqual(dest["secret"]["access_token"], "EAAB" + "t" * 40)
        self.assertEqual(dest["config"]["graph_version"], "v26.0")

    def test_revoked_keys_are_left_out(self):
        api_key, _ = ApiKey.issue(self.site, "Old")
        api_key.revoked_at = api_key.created_at
        api_key.save()
        publish.publish_site(self.site.pk, self.redis)
        self.assertEqual(self.site_json()["api_keys"], {})

    def test_removed_domain_and_destination_disappear(self):
        publish.publish_site(self.site.pk, self.redis)
        dest_id = self.destination.pk
        self.domain.delete()
        self.destination.delete()
        publish.publish_site(self.site.pk, self.redis)
        self.assertIsNone(self.redis.get("cfg:host:data.shop.com"))
        self.assertIsNone(self.redis.get(f"cfg:dest:{dest_id}"))
        self.assertEqual(self.site_json()["hosts"], [])

    def test_paused_site_is_still_published(self):
        self.site.status = Site.PAUSED
        self.site.save()
        publish.publish_site(self.site.pk, self.redis)
        self.assertEqual(self.site_json()["status"], "paused")
        self.assertEqual(self.redis.get("cfg:host:data.shop.com"), str(self.site.pk))

    def test_deleted_site_is_removed(self):
        publish.publish_site(self.site.pk, self.redis)
        site_id = self.site.pk
        self.site.delete()
        publish.publish_site(site_id, self.redis)
        self.assertEqual(self.redis.scan_iter("cfg:*"), [])

    def test_publish_all_cleans_up_leftovers(self):
        self.redis.set("cfg:site:999", json.dumps({"hosts": ["old.gone.com"], "destinations": [{"id": 555}]}))
        self.redis.set("cfg:host:old.gone.com", 999)
        self.redis.set("cfg:host:stray.example.com", 1)
        self.redis.set("cfg:dest:555", "x")
        with mock.patch.object(publish, "get_redis", return_value=self.redis):
            call_command("publish_all", stdout=io.StringIO())
        self.assertEqual(sorted(self.redis.scan_iter("cfg:*")), sorted([
            f"cfg:site:{self.site.pk}", "cfg:host:data.shop.com", f"cfg:dest:{self.destination.pk}",
        ]))

    def test_saving_publishes_after_commit_with_a_new_version(self):
        with mock.patch.object(publish, "get_redis", return_value=self.redis):
            with self.captureOnCommitCallbacks(execute=True):
                Domain.objects.create(site=self.site, hostname="t.shop.com", status=Domain.VERIFIED)
        self.site.refresh_from_db()
        self.assertEqual(self.site.config_version, 2)
        self.assertEqual(self.redis.get("cfg:host:t.shop.com"), str(self.site.pk))
        self.assertEqual(self.site_json()["version"], 2)

    def test_redis_being_down_never_breaks_a_save(self):
        broken = mock.Mock()
        broken.get.side_effect = ConnectionError("redis down")
        with mock.patch.object(publish, "get_redis", return_value=broken), self.assertLogs("common.publish", "ERROR"):
            with self.captureOnCommitCallbacks(execute=True):
                self.site.name = "Renamed"
                self.site.save()
        self.assertEqual(Site.objects.get().name, "Renamed")
