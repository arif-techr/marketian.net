from django.db import models
from django.urls import reverse
from django.utils.text import slugify


class SiteProfile(models.Model):
    """Single row holding the owner's details shown across the site."""

    name = models.CharField(max_length=120, default="Your Name")
    role = models.CharField(max_length=160, default="Digital Marketer & Web Developer")
    tagline = models.CharField(
        max_length=255,
        default="I help brands grow with data-driven marketing and websites that convert.",
    )
    short_bio = models.TextField(blank=True)
    about = models.TextField(blank=True, help_text="Longer story for the About page. Blank lines start new paragraphs.")
    photo = models.ImageField(upload_to="profile/", blank=True)
    resume = models.FileField(upload_to="resume/", blank=True)
    email = models.EmailField(default="hello@marketian.net")
    phone = models.CharField(max_length=40, blank=True)
    whatsapp = models.CharField(max_length=40, blank=True, help_text="Number with country code, digits only, e.g. 8801XXXXXXXXX")
    location = models.CharField(max_length=120, blank=True)
    available_for_work = models.BooleanField(default=True)

    years_experience = models.PositiveIntegerField(default=5)
    projects_completed = models.PositiveIntegerField(default=50)
    happy_clients = models.PositiveIntegerField(default=30)

    linkedin = models.URLField(blank=True)
    github = models.URLField(blank=True)
    facebook = models.URLField(blank=True)
    twitter = models.URLField(blank=True, verbose_name="X / Twitter")
    instagram = models.URLField(blank=True)
    youtube = models.URLField(blank=True)

    class Meta:
        verbose_name = "Site profile"
        verbose_name_plural = "Site profile"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    @property
    def initials(self):
        return "".join(part[0] for part in self.name.split()[:2]).upper() or "M"

    @property
    def about_paragraphs(self):
        return [p.strip() for p in self.about.split("\n\n") if p.strip()]


class Service(models.Model):
    ICONS = [
        ("chart", "Chart / Analytics"),
        ("megaphone", "Megaphone / Ads"),
        ("search", "Search / SEO"),
        ("code", "Code / Development"),
        ("pen", "Pen / Content"),
        ("share", "Share / Social"),
        ("mail", "Mail / Email marketing"),
        ("palette", "Palette / Design"),
    ]

    title = models.CharField(max_length=120)
    icon = models.CharField(max_length=20, choices=ICONS, default="chart")
    summary = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    features = models.TextField(blank=True, help_text="One feature per line.")
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "title"]

    def __str__(self):
        return self.title

    @property
    def feature_list(self):
        return [line.strip() for line in self.features.splitlines() if line.strip()]


class Tool(models.Model):
    """A Marketian marketing tool (an app on its own subdomain), listed on the Marketing tools page."""

    LIVE, INVITE, BETA, SOON = "live", "invite", "beta", "soon"
    STATUSES = [(LIVE, "Live"), (INVITE, "Invite only"), (BETA, "Beta"), (SOON, "Coming soon")]
    ICONS = Service.ICONS + [("whatsapp", "WhatsApp")]

    name = models.CharField(max_length=80)
    icon = models.CharField(max_length=20, choices=ICONS, default="chart")
    tagline = models.CharField(max_length=160, help_text="One line: what it does.")
    description = models.TextField(blank=True)
    features = models.TextField(blank=True, help_text="One feature per line.")
    url = models.URLField(blank=True, help_text="Where it lives, e.g. https://wa.marketian.net")
    status = models.CharField(max_length=10, choices=STATUSES, default=LIVE,
                              help_text="Coming soon: no Open button, visitors can ask to be told when it's ready.")
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True, help_text="Show it on the site.")

    class Meta:
        ordering = ["order", "name"]

    def __str__(self):
        return self.name

    @property
    def feature_list(self):
        return [line.strip() for line in self.features.splitlines() if line.strip()]

    @property
    def can_open(self):
        return self.status != self.SOON and bool(self.url)


class Project(models.Model):
    title = models.CharField(max_length=160)
    slug = models.SlugField(max_length=180, unique=True, blank=True)
    category = models.CharField(max_length=80, help_text="e.g. SEO, Web Development, Paid Ads")
    client = models.CharField(max_length=120, blank=True)
    summary = models.CharField(max_length=255)
    challenge = models.TextField(blank=True)
    solution = models.TextField(blank=True)
    results = models.TextField(blank=True, help_text="One result per line, e.g. '+240% organic traffic'.")
    cover = models.ImageField(upload_to="projects/", blank=True)
    accent = models.CharField(max_length=7, default="#6d5efc", help_text="Hex color used when there is no cover image.")
    tags = models.CharField(max_length=255, blank=True, help_text="Comma separated.")
    live_url = models.URLField(blank=True)
    completed = models.DateField(null=True, blank=True)
    featured = models.BooleanField(default=False, help_text="Show on the home page.")
    order = models.PositiveIntegerField(default=0)
    is_published = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "-completed", "title"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title)[:170] or "project"
            slug, n = base, 2
            while Project.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug, n = f"{base}-{n}", n + 1
            self.slug = slug
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("core:project_detail", args=[self.slug])

    @property
    def tag_list(self):
        return [t.strip() for t in self.tags.split(",") if t.strip()]

    @property
    def result_list(self):
        return [line.strip() for line in self.results.splitlines() if line.strip()]


class Skill(models.Model):
    name = models.CharField(max_length=80)
    level = models.PositiveIntegerField(default=80, help_text="0–100")
    group = models.CharField(max_length=60, default="Marketing")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["group", "order", "name"]

    def __str__(self):
        return self.name


class Experience(models.Model):
    title = models.CharField(max_length=120)
    organization = models.CharField(max_length=120)
    period = models.CharField(max_length=60, help_text="e.g. 2022 — Present")
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order"]
        verbose_name_plural = "Experience"

    def __str__(self):
        return f"{self.title} — {self.organization}"


class Testimonial(models.Model):
    name = models.CharField(max_length=120)
    position = models.CharField(max_length=160, blank=True)
    quote = models.TextField()
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return self.name

    @property
    def initials(self):
        return "".join(part[0] for part in self.name.split()[:2]).upper()


class ContactMessage(models.Model):
    name = models.CharField(max_length=120)
    email = models.EmailField()
    phone = models.CharField(max_length=40, blank=True)
    subject = models.CharField(max_length=200)
    budget = models.CharField(max_length=40, blank=True)
    message = models.TextField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    email_sent = models.BooleanField(default=False, verbose_name="Notified me")
    replied_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name}: {self.subject}"
