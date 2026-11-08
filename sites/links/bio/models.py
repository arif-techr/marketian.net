"""Link-in-bio pages: links.marketian.net/@name, one per person."""
import re
from urllib.parse import parse_qs, urlsplit

from django.conf import settings
from django.db import models
from django.utils import timezone

# Look presets. "custom" uses the page's own colours.
THEMES = {
    "light": {"label": "Light", "bg": "#f4f5fb", "text": "#12152a", "button": "#ffffff", "button_text": "#12152a"},
    "dark": {"label": "Dark", "bg": "#0b0d17", "text": "#eef0f7", "button": "#1c2133", "button_text": "#eef0f7"},
    "marketian": {"label": "Marketian", "bg": "linear-gradient(160deg, #6d5efc, #22d3ee)", "text": "#ffffff", "button": "#ffffff", "button_text": "#2b2470"},
    "sunset": {"label": "Sunset", "bg": "linear-gradient(160deg, #f97316, #db2777)", "text": "#ffffff", "button": "rgba(255, 255, 255, .92)", "button_text": "#7c2d12"},
    "forest": {"label": "Forest", "bg": "#14532d", "text": "#ecfdf5", "button": "#22c55e", "button_text": "#052e16"},
    "ocean": {"label": "Ocean", "bg": "linear-gradient(180deg, #0c4a6e, #0e7490)", "text": "#f0f9ff", "button": "#38bdf8", "button_text": "#082f49"},
    "custom": {"label": "My own colours"},
}
BUTTON_STYLES = [("rounded", "Rounded"), ("pill", "Pill"), ("square", "Square"), ("outline", "Outline"), ("shadow", "Shadow")]
# (field, label, how the address is made from what was typed)
SOCIALS = [
    ("instagram", "Instagram", "https://instagram.com/{}"),
    ("facebook", "Facebook", "https://facebook.com/{}"),
    ("tiktok", "TikTok", "https://www.tiktok.com/@{}"),
    ("youtube", "YouTube", "https://youtube.com/@{}"),
    ("x", "X / Twitter", "https://x.com/{}"),
    ("linkedin", "LinkedIn", "https://www.linkedin.com/in/{}"),
    ("github", "GitHub", "https://github.com/{}"),
    ("whatsapp", "WhatsApp", "https://wa.me/{}"),
    ("email", "Email", "mailto:{}"),
    ("website", "Website", "{}"),
]
HANDLE_RE = re.compile(r"^[a-z0-9][a-z0-9_.]{1,29}$")


class Page(models.Model):
    owner = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="bio_page")
    handle = models.CharField(max_length=30, unique=True, help_text="links.marketian.net/@handle")
    title = models.CharField(max_length=80, help_text="Your name or brand, shown at the top.")
    bio = models.CharField(max_length=200, blank=True)
    avatar = models.ImageField(upload_to="avatars/", blank=True)
    theme = models.CharField(max_length=20, default="light", choices=[(k, v["label"]) for k, v in THEMES.items()])
    button_style = models.CharField(max_length=20, default="rounded", choices=BUTTON_STYLES)
    bg_color = models.CharField(max_length=7, default="#f4f5fb")
    text_color = models.CharField(max_length=7, default="#12152a")
    button_color = models.CharField(max_length=7, default="#6d5efc")
    button_text_color = models.CharField(max_length=7, default="#ffffff")
    is_published = models.BooleanField(default=True, help_text="Off: visitors see 'not available'.")
    sensitive = models.BooleanField(default=False, help_text="Visitors confirm they want to see the page first (18+ content).")
    collect_emails = models.BooleanField(default=False, help_text="Show an email sign-up form on the page.")
    email_prompt = models.CharField(max_length=120, default="Get my news by email")
    views = models.PositiveIntegerField(default=0, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    instagram = models.CharField(max_length=100, blank=True)
    facebook = models.CharField(max_length=100, blank=True)
    tiktok = models.CharField(max_length=100, blank=True)
    youtube = models.CharField(max_length=100, blank=True)
    x = models.CharField(max_length=100, blank=True)
    linkedin = models.CharField(max_length=100, blank=True)
    github = models.CharField(max_length=100, blank=True)
    whatsapp = models.CharField(max_length=20, blank=True, help_text="Number with country code, digits only.")
    email = models.EmailField(blank=True)
    website = models.URLField(blank=True)

    def __str__(self):
        return f"@{self.handle}"

    @property
    def colors(self):
        if self.theme == "custom":
            return {"bg": self.bg_color, "text": self.text_color, "button": self.button_color, "button_text": self.button_text_color}
        return THEMES.get(self.theme, THEMES["light"])

    @property
    def social_links(self):
        out = []
        for field, label, pattern in SOCIALS:
            value = getattr(self, field).strip()
            if value:
                url = value if value.startswith(("http://", "https://")) else pattern.format(value.lstrip("@"))
                out.append({"key": field, "label": label, "url": url})
        return out

    def visible_items(self):
        now = timezone.now()
        return [item for item in self.items.all() if item.is_visible(now)]


class Item(models.Model):
    LINK, HEADER, VIDEO = "link", "header", "video"
    KINDS = [(LINK, "Link button"), (HEADER, "Section title"), (VIDEO, "YouTube video")]

    page = models.ForeignKey(Page, on_delete=models.CASCADE, related_name="items")
    kind = models.CharField(max_length=10, choices=KINDS, default=LINK)
    title = models.CharField(max_length=100)
    url = models.URLField(max_length=2000, blank=True)
    position = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    show_from = models.DateTimeField(null=True, blank=True)
    show_until = models.DateTimeField(null=True, blank=True)
    clicks = models.PositiveIntegerField(default=0, editable=False)

    class Meta:
        ordering = ["position", "id"]

    def __str__(self):
        return self.title

    def is_visible(self, now=None):
        now = now or timezone.now()
        return (self.is_active and (not self.show_from or self.show_from <= now)
                and (not self.show_until or self.show_until > now))

    @property
    def schedule_state(self):
        now = timezone.now()
        if self.show_from and self.show_from > now:
            return "Scheduled"
        if self.show_until and self.show_until <= now:
            return "Ended"
        return ""

    @property
    def youtube_id(self):
        parts = urlsplit(self.url)
        host = (parts.hostname or "").removeprefix("www.").removeprefix("m.")
        if host == "youtu.be":
            vid = parts.path.strip("/")
        elif host in ("youtube.com", "youtube-nocookie.com"):
            vid = parse_qs(parts.query).get("v", [""])[0] or parts.path.rsplit("/", 1)[-1]
        else:
            return ""
        return vid if re.fullmatch(r"[A-Za-z0-9_-]{6,20}", vid) else ""


class Event(models.Model):
    """A page view or a click on one of its buttons. No IP addresses are kept."""

    VIEW, CLICK = "view", "click"
    page = models.ForeignKey(Page, on_delete=models.CASCADE, related_name="events")
    item = models.ForeignKey(Item, on_delete=models.SET_NULL, null=True, blank=True, related_name="events")
    kind = models.CharField(max_length=5, choices=[(VIEW, "View"), (CLICK, "Click")])
    at = models.DateTimeField(default=timezone.now)
    visitor = models.CharField(max_length=16)
    referrer = models.CharField(max_length=200, blank=True)
    device = models.CharField(max_length=10)
    browser = models.CharField(max_length=30)
    os = models.CharField(max_length=30)

    class Meta:
        ordering = ["-at"]
        indexes = [models.Index(fields=["page", "kind", "at"])]


class Subscriber(models.Model):
    page = models.ForeignKey(Page, on_delete=models.CASCADE, related_name="subscribers")
    email = models.EmailField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["page", "email"], name="one_signup_per_email")]
