"""Short links and the clicks on them."""
import secrets
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db import models
from django.utils import timezone

# No look-alike characters (l/1, o/0), so a short link can be read out loud or typed from print.
ALPHABET = "abcdefghijkmnpqrstuvwxyz23456789"
# Paths the app itself uses: never a short link.
RESERVED = {"admin", "accounts", "app", "login", "logout", "static", "media", "api", "o", "health"}


class Link(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="links")
    slug = models.SlugField(max_length=60, unique=True, help_text="The part after the slash, always lowercase.")
    destination = models.URLField(max_length=2000)
    title = models.CharField(max_length=200, blank=True)
    password = models.CharField(max_length=128, blank=True, help_text="Hashed. Empty: no password.")
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True, help_text="Turned off: visitors see a notice instead of being sent on.")
    clicks = models.PositiveIntegerField(default=0, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.slug

    @classmethod
    def new_slug(cls):
        for length in (6, 6, 6, 7, 8):
            slug = "".join(secrets.choice(ALPHABET) for _ in range(length))
            if slug not in RESERVED and not cls.objects.filter(slug=slug).exists():
                return slug
        raise RuntimeError("Could not find a free short name.")

    @property
    def label(self):
        return self.title or urlsplit(self.destination).netloc

    @property
    def is_expired(self):
        return bool(self.expires_at and self.expires_at <= timezone.now())

    @property
    def has_password(self):
        return bool(self.password)

    def set_password(self, raw):
        self.password = make_password(raw) if raw else ""

    def check_password(self, raw):
        return self.has_password and check_password(raw, self.password)


class Click(models.Model):
    """One visit through a short link. No IP addresses are kept."""

    link = models.ForeignKey(Link, on_delete=models.CASCADE, related_name="click_set")
    at = models.DateTimeField(default=timezone.now)
    # Hash of the visitor's IP and browser, new every day: counts unique visits without storing who.
    visitor = models.CharField(max_length=16)
    referrer = models.CharField(max_length=200, blank=True, help_text="Domain of the page the visitor came from.")
    device = models.CharField(max_length=10)
    browser = models.CharField(max_length=30)
    os = models.CharField(max_length=30)

    class Meta:
        ordering = ["-at"]
        indexes = [models.Index(fields=["link", "at"])]
