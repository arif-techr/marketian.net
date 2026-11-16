"""
A Site is one client website. Its events arrive at the edge on one of its Domains
(data.shop.com, pointed at edge.marketian.net), under a random path prefix and
loader file name, so ad blockers have no fixed word to match. ApiKeys let the
client's own server send events (orders, refunds) too.
"""

import hashlib
import re
import secrets
import string

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from workspaces.models import Workspace

BASE62 = string.digits + string.ascii_letters
LOWER36 = string.digits + string.ascii_lowercase

# Never part of a path prefix or loader name: these are what block lists look for.
BLOCKED_WORDS = (
    "ad", "ads", "analytic", "beacon", "collect", "count", "event", "fb", "ga", "gtm", "hit",
    "log", "metric", "pix", "px", "spy", "stat", "tag", "track", "utm",
)

HOSTNAME_RE = re.compile(r"^(?=.{1,253}$)(?!-)[a-z0-9-]{1,63}(?<!-)(\.(?!-)[a-z0-9-]{1,63}(?<!-))+$")


def random_text(length, alphabet=BASE62):
    return "".join(secrets.choice(alphabet) for _ in range(length))


def has_blocked_word(text):
    text = text.lower()
    return any(word in text for word in BLOCKED_WORDS)


def safe_random_name(length):
    """Random [a-z0-9] text that contains no blocked word and doesn't start with a digit."""
    while True:
        name = random_text(length, LOWER36)
        if name[0].isalpha() and not has_blocked_word(name):
            return name


def new_public_key():
    return f"mt_pk_{random_text(18)}"


def new_loader_name():
    return f"{safe_random_name(3)}.js"


def new_verify_token():
    return random_text(32)


def normalise_hostname(value):
    """ "https://Shop.com/" → "shop.com". Raises ValidationError if it isn't a host name."""
    host = (value or "").strip().lower()
    host = re.sub(r"^[a-z]+://", "", host).split("/")[0].split("?")[0].rstrip(".")
    if ":" in host or not HOSTNAME_RE.match(host):
        raise ValidationError(f"{value!r} isn't a domain name like shop.com.")
    return host


class Site(models.Model):
    WORKSPACE_FIELD = "workspace"

    CONSENT_OFF, CONSENT_BASIC, CONSENT_ADVANCED = "off", "basic", "advanced"
    CONSENT_MODES = [
        (CONSENT_OFF, "Off: treat every visitor as consenting"),
        (CONSENT_BASIC, "Basic: wait for a consent signal from the page"),
        (CONSENT_ADVANCED, "Advanced: cookieless pings to Google before consent"),
    ]
    ACTIVE, PAUSED = "active", "paused"

    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="sites")
    name = models.CharField(max_length=120)
    primary_domain = models.CharField(max_length=253, help_text="The shop's own domain, like shop.com. Sets the cookie domain and which pages may send events.")
    public_key = models.CharField(max_length=24, unique=True, default=new_public_key, editable=False)
    path_prefix = models.CharField(max_length=8, unique=True, editable=False)
    loader_name = models.CharField(max_length=12, default=new_loader_name, editable=False)
    timezone = models.CharField(max_length=40, default="Asia/Dhaka")
    default_currency = models.CharField(max_length=3, default="BDT")
    consent_mode = models.CharField(max_length=12, choices=CONSENT_MODES, default=CONSENT_OFF)
    bot_filter = models.BooleanField(default=True)
    cookie_keeper = models.BooleanField(default=True)
    status = models.CharField(max_length=10, choices=[(ACTIVE, "Active"), (PAUSED, "Paused")], default=ACTIVE)
    config_version = models.PositiveIntegerField(default=1)  # the edge's cache key; +1 on every change
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["workspace", "name"], name="unique_site_name_per_workspace")]

    def __str__(self):
        return self.name

    def clean(self):
        if self.primary_domain:
            try:
                self.primary_domain = normalise_hostname(self.primary_domain)
            except ValidationError as exc:
                raise ValidationError({"primary_domain": exc.messages})
        self.default_currency = (self.default_currency or "").upper()
        if not re.fullmatch(r"[A-Z]{3}", self.default_currency):
            raise ValidationError({"default_currency": "Use a three-letter currency code like BDT or USD."})

    def save(self, *args, **kwargs):
        if not self.path_prefix:
            self.path_prefix = self.new_path_prefix()
        super().save(*args, **kwargs)

    @classmethod
    def new_path_prefix(cls):
        while True:
            prefix = safe_random_name(secrets.choice((4, 5, 6)))
            if not cls.objects.filter(path_prefix=prefix).exists():
                return prefix

    def covers(self, hostname):
        """True if `hostname` is the primary domain or one of its subdomains."""
        return hostname == self.primary_domain or hostname.endswith("." + self.primary_domain)


class Domain(models.Model):
    WORKSPACE_FIELD = "site__workspace"

    SUBDOMAIN, SAME_ORIGIN = "subdomain", "same_origin"
    PENDING, VERIFIED, FAILING, DISABLED = "pending", "verified", "failing", "disabled"
    STATUSES = [(PENDING, "Waiting for DNS"), (VERIFIED, "Verified"), (FAILING, "Failing"), (DISABLED, "Disabled")]

    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="domains")
    hostname = models.CharField(max_length=253, unique=True)
    mode = models.CharField(max_length=12, choices=[(SUBDOMAIN, "Subdomain"), (SAME_ORIGIN, "Same origin")], default=SUBDOMAIN)
    status = models.CharField(max_length=10, choices=STATUSES, default=PENDING)
    verify_token = models.CharField(max_length=32, default=new_verify_token, editable=False)
    dns_seen = models.JSONField(default=dict, blank=True)  # last lookup: {"cname": "...", "a": ["..."]}
    verified_at = models.DateTimeField(null=True, blank=True)
    last_checked_at = models.DateTimeField(null=True, blank=True)
    fail_count = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["hostname"]

    def __str__(self):
        return self.hostname

    def clean(self):
        try:
            self.hostname = normalise_hostname(self.hostname)
        except ValidationError as exc:
            raise ValidationError({"hostname": exc.messages})
        if self.site_id and not self.site.covers(self.hostname):
            raise ValidationError({"hostname": f"Use {self.site.primary_domain} or a subdomain of it, like data.{self.site.primary_domain}."})
        if self.mode == self.SUBDOMAIN and self.site_id and self.hostname == self.site.primary_domain:
            raise ValidationError({"hostname": f"Use a subdomain such as data.{self.site.primary_domain}: the shop itself stays where it is."})

    @property
    def serves_events(self):
        """Caddy may get a certificate and the edge answers for this host."""
        return self.status in (self.VERIFIED, self.FAILING)


class ApiKey(models.Model):
    """A key for server-to-server events. Only its SHA-256 is kept; the key is shown once."""

    WORKSPACE_FIELD = "site__workspace"

    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="api_keys")
    name = models.CharField(max_length=60)
    prefix = models.CharField(max_length=12, unique=True)  # "mtk_ab12cd": shown so people can tell keys apart
    key_hash = models.CharField(max_length=64)
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.prefix})"

    @staticmethod
    def hash(key):
        return hashlib.sha256(key.encode()).hexdigest()

    @classmethod
    def issue(cls, site, name, user=None):
        """Make a key. Returns (api_key, full_key): show full_key once, it can't be seen again."""
        while True:
            prefix = f"mtk_{random_text(6)}"
            if not cls.objects.filter(prefix=prefix).exists():
                break
        full_key = f"{prefix}_{random_text(32)}"
        api_key = cls.objects.create(site=site, name=name, prefix=prefix, key_hash=cls.hash(full_key), created_by=user)
        return api_key, full_key

    @property
    def is_active(self):
        return self.revoked_at is None
