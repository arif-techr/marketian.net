"""
Publishes each site's configuration to Redis, where the edge and worker read it.
The edge never touches PostgreSQL, so collection keeps working while it's down.

  cfg:host:{hostname}  → site id               (verified/failing domains only)
  cfg:site:{id}        → JSON, no secrets      (edge: prefix, loader, consent, hosts, key hashes)
  cfg:dest:{id}        → encrypted JSON        (worker: settings + secret)
  cfg:changed          ← pub/sub, message = site id: drop it from memory caches

Saving or deleting a site, domain, API key or destination publishes its site once
the transaction commits (signals at the bottom). `manage.py publish_all` rebuilds
everything after a deploy or a Redis loss.
"""

import json
import logging

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.db.models.signals import post_delete, post_save

from . import crypto

log = logging.getLogger(__name__)

CHANNEL = "cfg:changed"
_client = None


def get_redis():
    global _client
    if _client is None:
        import redis

        _client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True, socket_timeout=5, socket_connect_timeout=3)
    return _client


def host_key(hostname):
    return f"cfg:host:{hostname}"


def site_key(site_id):
    return f"cfg:site:{site_id}"


def dest_key(dest_id):
    return f"cfg:dest:{dest_id}"


def site_config(site):
    """What the edge needs about a site. Never holds a secret."""
    return {
        "id": site.pk,
        "version": site.config_version,
        "status": site.status,
        "public_key": site.public_key,
        "prefix": site.path_prefix,
        "loader": site.loader_name,
        "primary_domain": site.primary_domain,
        "hosts": sorted(d.hostname for d in site.domains.all() if d.serves_events),
        "verify_tokens": {d.hostname: d.verify_token for d in site.domains.all() if d.mode == d.SAME_ORIGIN},
        "consent_mode": site.consent_mode,
        "bot_filter": site.bot_filter,
        "cookie_keeper": site.cookie_keeper,
        "timezone": site.timezone,
        "currency": site.default_currency,
        "api_keys": {k.prefix: k.key_hash for k in site.api_keys.all() if k.is_active},
        "destinations": [
            {
                "id": d.pk,
                "type": d.type,
                "enabled": d.enabled,
                "event_map": d.effective_event_map(),
                "consent_required": d.consent_required,
                "send_pii": d.send_pii,
            }
            for d in site.destinations.all()
        ],
    }


def destination_config(destination):
    """What the worker needs to send: settings and the secret, encrypted as one value."""
    payload = {
        "id": destination.pk,
        "site_id": destination.site_id,
        "type": destination.type,
        "config": destination.config,
        "secret": destination.get_secret(),
    }
    if destination.type == "meta":
        payload["config"] = {"graph_version": settings.META_GRAPH_VERSION} | destination.config
    return crypto.encrypt(json.dumps(payload))


def publish_site(site_id, client=None):
    """Write (or remove) everything Redis holds for one site, then tell the edge and worker."""
    from tracker.models import Site

    client = client or get_redis()
    site = Site.objects.filter(pk=site_id).prefetch_related("domains", "api_keys", "destinations").first()

    previous = client.get(site_key(site_id))
    previous = json.loads(previous) if previous else {}
    old_hosts = set(previous.get("hosts", []))
    old_dests = {d["id"] for d in previous.get("destinations", [])}

    pipe = client.pipeline(transaction=True)
    if site is None:
        new_hosts, new_dests = set(), set()
        pipe.delete(site_key(site_id))
    else:
        config = site_config(site)
        new_hosts = set(config["hosts"])
        new_dests = {d["id"] for d in config["destinations"]}
        pipe.set(site_key(site_id), json.dumps(config))
        for hostname in new_hosts:
            pipe.set(host_key(hostname), site_id)
        for destination in site.destinations.all():
            pipe.set(dest_key(destination.pk), destination_config(destination))
    for hostname in old_hosts - new_hosts:
        pipe.delete(host_key(hostname))
    for dest_id in old_dests - new_dests:
        pipe.delete(dest_key(dest_id))
    pipe.publish(CHANNEL, site_id)
    pipe.execute()


def publish_all(client=None):
    """Publish every site and remove keys of sites, hosts and destinations that no longer exist."""
    from destinations.models import Destination
    from tracker.models import Domain, Site

    client = client or get_redis()
    site_ids = set(Site.objects.values_list("pk", flat=True))
    published = set()
    for key in client.scan_iter("cfg:site:*"):
        published.add(int(key.rsplit(":", 1)[1]))
    for site_id in sorted(site_ids | published):
        publish_site(site_id, client)

    serving = {d.hostname for d in Domain.objects.select_related("site") if d.serves_events}
    stale = [key for key in client.scan_iter("cfg:host:*") if key.split(":", 2)[2] not in serving]
    dest_ids = set(Destination.objects.values_list("pk", flat=True))
    stale += [key for key in client.scan_iter("cfg:dest:*") if int(key.rsplit(":", 1)[1]) not in dest_ids]
    if stale:
        client.delete(*stale)
    return len(site_ids)


def bump_and_publish(site_id):
    """After a change: new config_version (the edge's cache key), then publish. Never breaks the save."""
    from tracker.models import Site

    Site.objects.filter(pk=site_id).update(config_version=F("config_version") + 1)
    try:
        publish_site(site_id)
    except Exception:
        log.exception("Couldn't publish site %s to Redis; run `manage.py publish_all` once Redis is back.", site_id)


def _site_id_of(instance):
    return instance.pk if instance._meta.model_name == "site" else instance.site_id


def _changed(sender, instance, **kwargs):
    site_id = _site_id_of(instance)
    transaction.on_commit(lambda: bump_and_publish(site_id))


def connect_signals():
    from destinations.models import Destination
    from tracker.models import ApiKey, Domain, Site

    for model in (Site, Domain, ApiKey, Destination):
        post_save.connect(_changed, sender=model, dispatch_uid=f"publish-{model._meta.label}-save")
        post_delete.connect(_changed, sender=model, dispatch_uid=f"publish-{model._meta.label}-delete")
