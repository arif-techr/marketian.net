import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django import forms
from django.conf import settings
from django.utils import timezone

from .models import RESERVED, Link

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,59}$")
UTM_FIELDS = ["utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content"]


def add_utm(url, tags):
    """Add the filled-in UTM tags to the address, replacing any it already has."""
    tags = {k: v for k, v in tags.items() if v}
    if not tags:
        return url
    parts = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k not in tags]
    return urlunsplit(parts._replace(query=urlencode(query + list(tags.items()))))


class LinkFields(forms.ModelForm):
    """What creating and editing a link have in common."""

    destination = forms.URLField(max_length=2000, assume_scheme="https", label="Long link",
                                 widget=forms.URLInput(attrs={"placeholder": "https://example.com/a-very-long-page"}))
    slug = forms.CharField(required=False, max_length=60, label="Custom name",
                           help_text="Letters, numbers, - and _. Leave empty for a random one.")
    expires_at = forms.DateTimeField(required=False, label="Stops working on",
                                     widget=forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"))

    class Meta:
        model = Link
        fields = ["destination", "slug", "title", "expires_at"]
        labels = {"title": "Title (only you see it)"}

    def __init__(self, *args, short_host="", **kwargs):
        super().__init__(*args, **kwargs)
        self.short_host = short_host.split(":")[0].lower()

    def clean_destination(self):
        url = self.cleaned_data["destination"].strip()
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https"):
            raise forms.ValidationError("Only web addresses (http or https) can be shortened.")
        if (parts.hostname or "").lower() == self.short_host:
            raise forms.ValidationError("That's already a short link here.")
        return url

    def clean_slug(self):
        slug = self.cleaned_data["slug"].strip().lower()
        if not slug:
            return ""
        if not SLUG_RE.match(slug):
            raise forms.ValidationError("Use 2 to 60 letters, numbers, - or _ (starting with a letter or number).")
        if slug in RESERVED:
            raise forms.ValidationError("That name is reserved. Try another.")
        if Link.objects.filter(slug=slug).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("That name is taken. Try another.")
        return slug

    def clean_expires_at(self):
        when = self.cleaned_data["expires_at"]
        if when and when <= timezone.now():
            raise forms.ValidationError("Pick a time in the future.")
        return when


class CreateLinkForm(LinkFields):
    password = forms.CharField(required=False, label="Password", strip=False,
                               help_text="Visitors must type it before they are sent on.",
                               widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))
    utm_source = forms.CharField(required=False, max_length=100, label="Source", widget=forms.TextInput(attrs={"placeholder": "facebook"}))
    utm_medium = forms.CharField(required=False, max_length=100, label="Medium", widget=forms.TextInput(attrs={"placeholder": "social"}))
    utm_campaign = forms.CharField(required=False, max_length=100, label="Campaign", widget=forms.TextInput(attrs={"placeholder": "summer-sale"}))
    utm_term = forms.CharField(required=False, max_length=100, label="Term")
    utm_content = forms.CharField(required=False, max_length=100, label="Content")

    def __init__(self, *args, owner=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.owner = owner

    def clean(self):
        data = super().clean()
        today = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
        if self.owner and Link.objects.filter(owner=self.owner, created_at__gte=today).count() >= settings.LINKS_PER_DAY:
            raise forms.ValidationError(f"You've made {settings.LINKS_PER_DAY} links today, the most for one day. Try again tomorrow.")
        if data.get("destination"):
            data["destination"] = add_utm(data["destination"], {k: data.get(k, "") for k in UTM_FIELDS})
        return data

    def save(self, commit=True):
        link = super().save(commit=False)
        link.owner = self.owner
        link.slug = self.cleaned_data["slug"] or Link.new_slug()
        link.set_password(self.cleaned_data["password"])
        if commit:
            link.save()
        return link


class EditLinkForm(LinkFields):
    new_password = forms.CharField(required=False, label="New password", strip=False,
                                   help_text="Leave empty to keep the current one.",
                                   widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))
    remove_password = forms.BooleanField(required=False, label="Remove the password")

    class Meta(LinkFields.Meta):
        fields = LinkFields.Meta.fields + ["is_active"]
        labels = {**LinkFields.Meta.labels, "is_active": "Link is on"}

    def clean_slug(self):
        # Editing keeps the current name when the box is emptied.
        return super().clean_slug() or self.instance.slug

    def save(self, commit=True):
        link = super().save(commit=False)
        if self.cleaned_data["remove_password"]:
            link.set_password("")
        elif self.cleaned_data["new_password"]:
            link.set_password(self.cleaned_data["new_password"])
        if commit:
            link.save()
        return link
