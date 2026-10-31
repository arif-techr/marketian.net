from django.conf import settings
from django.db import models
from django.template import Engine, TemplateSyntaxError
from django.core.exceptions import ValidationError
from django.template.loader import render_to_string

PLACEHOLDER_HELP = (
    "Placeholders: {{ name }}, {{ first_name }}, {{ email }}, {{ subject }} (their subject), "
    "{{ message }} (their message), {{ my_name }}, {{ my_role }}, {{ my_email }}, {{ my_phone }}, "
    "{{ website }}, {{ today }}"
)


def validate_placeholders(value):
    try:
        Engine(autoescape=False).from_string(value)
    except TemplateSyntaxError as exc:
        raise ValidationError(f"Placeholder error: {exc}")


class EmailSignature(models.Model):
    label = models.CharField(max_length=80, default="Default", help_text="Only you see this name.")
    sign_off = models.CharField(max_length=80, default="Best regards,")
    full_name = models.CharField(max_length=120, blank=True, help_text="Blank = name from Site profile.")
    job_title = models.CharField(max_length=120, blank=True, help_text="Blank = role from Site profile.")
    company = models.CharField(max_length=120, default="Marketian")
    email = models.EmailField(blank=True, help_text="Blank = email from Site profile.")
    phone = models.CharField(max_length=40, blank=True, help_text="Blank = phone from Site profile.")
    website = models.CharField(max_length=120, default="marketian.net")
    show_photo = models.BooleanField(default=True, help_text="Uses the photo from Site profile (initials if none).")
    show_socials = models.BooleanField(default=True, help_text="Links from Site profile.")
    accent_color = models.CharField(max_length=7, default="#6d5efc")
    disclaimer = models.TextField(blank=True, help_text="Optional small print under the signature.")
    is_default = models.BooleanField(default=False)

    class Meta:
        ordering = ["-is_default", "label"]

    def __str__(self):
        return f"{self.label}{' (default)' if self.is_default else ''}"

    def save(self, *args, **kwargs):
        if not self.is_default and not EmailSignature.objects.exclude(pk=self.pk).filter(is_default=True).exists():
            self.is_default = True
        super().save(*args, **kwargs)
        if self.is_default:
            EmailSignature.objects.exclude(pk=self.pk).update(is_default=False)

    @classmethod
    def get_default(cls):
        return cls.objects.filter(is_default=True).first() or cls.objects.first()

    def context(self):
        from core.models import SiteProfile

        p = SiteProfile.load()
        website = self.website.strip()
        socials = [(label, url) for label, url in [
            ("LinkedIn", p.linkedin), ("Facebook", p.facebook), ("Instagram", p.instagram),
            ("X", p.twitter), ("YouTube", p.youtube), ("GitHub", p.github),
        ] if url] if self.show_socials else []
        return {
            "sig": self,
            "name": self.full_name or p.name,
            "title": self.job_title or p.role,
            "email": self.email or p.email,
            "phone": self.phone or p.phone,
            "website": website,
            "website_url": website if website.startswith("http") else f"https://{website}" if website else "",
            "photo_url": settings.SITE_URL.rstrip("/") + p.photo.url if self.show_photo and p.photo else "",
            "initials": p.initials if self.show_photo else "",
            "socials": socials,
        }

    def render_html(self):
        return render_to_string("mailer/signature.html", self.context())

    def render_text(self):
        return render_to_string("mailer/signature.txt", self.context()).strip()


class EmailTemplate(models.Model):
    REPLY = "reply"
    AUTO_REPLY = "auto_reply"
    GENERAL = "general"
    PURPOSES = [
        (REPLY, "Reply to a contact message"),
        (AUTO_REPLY, "Automatic reply to new messages"),
        (GENERAL, "General / outreach"),
    ]

    name = models.CharField(max_length=120)
    purpose = models.CharField(max_length=20, choices=PURPOSES, default=REPLY)
    subject = models.CharField(max_length=200, validators=[validate_placeholders], help_text=PLACEHOLDER_HELP)
    body = models.TextField(validators=[validate_placeholders], help_text=PLACEHOLDER_HELP + ". Plain text; links become clickable.")
    signature = models.ForeignKey(EmailSignature, null=True, blank=True, on_delete=models.SET_NULL, help_text="Blank = default signature.")
    is_active = models.BooleanField(default=True, help_text="Only one automatic-reply template can be active.")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["purpose", "name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.purpose == self.AUTO_REPLY and self.is_active:
            EmailTemplate.objects.filter(purpose=self.AUTO_REPLY).exclude(pk=self.pk).update(is_active=False)


class SentEmail(models.Model):
    KINDS = [
        ("reply", "Reply"),
        ("compose", "New email"),
        ("bulk", "Bulk"),
        ("auto_reply", "Auto-reply"),
        ("notification", "Notification to me"),
        ("test", "Test"),
    ]
    SENT, FAILED = "sent", "failed"

    kind = models.CharField(max_length=20, choices=KINDS)
    to = models.TextField()
    cc = models.TextField(blank=True)
    subject = models.CharField(max_length=255)
    body = models.TextField()
    html = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=[(SENT, "Sent"), (FAILED, "Failed")])
    error = models.TextField(blank=True)
    template = models.ForeignKey(EmailTemplate, null=True, blank=True, on_delete=models.SET_NULL)
    contact = models.ForeignKey("core.ContactMessage", null=True, blank=True, on_delete=models.SET_NULL, related_name="emails")
    sent_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Sent email"

    def __str__(self):
        return f"{self.subject} → {self.to}"
