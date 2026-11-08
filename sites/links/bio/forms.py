import io
import re

from django import forms
from django.core.files.base import ContentFile
from PIL import Image, ImageOps

from .models import HANDLE_RE, SOCIALS, Item, Page

MAX_PHOTO_MB = 5
COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
DATETIME = forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M")


class HandleMixin:
    def clean_handle(self):
        handle = self.cleaned_data["handle"].strip().lstrip("@").lower()
        if not HANDLE_RE.match(handle):
            raise forms.ValidationError("Use 2 to 30 letters, numbers, . or _ (starting with a letter or number).")
        if Page.objects.filter(handle=handle).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("That name is taken. Try another.")
        return handle


class CreatePageForm(HandleMixin, forms.ModelForm):
    class Meta:
        model = Page
        fields = ["handle", "title"]
        labels = {"handle": "Your page name", "title": "Name shown on the page"}


class ProfileForm(forms.ModelForm):
    remove_avatar = forms.BooleanField(required=False, label="Remove the photo")

    class Meta:
        model = Page
        fields = ["title", "bio", "avatar"]
        labels = {"title": "Name or brand", "bio": "Short bio", "avatar": "Photo"}
        widgets = {"bio": forms.Textarea(attrs={"rows": 3, "maxlength": 200})}

    def clean_avatar(self):
        photo = self.cleaned_data.get("avatar")
        if not photo or not hasattr(photo, "content_type"):
            return photo  # unchanged
        if photo.size > MAX_PHOTO_MB * 1024 * 1024:
            raise forms.ValidationError(f"Choose a photo under {MAX_PHOTO_MB} MB.")
        # A small square JPEG: loads fast on phones, and drops anything hidden in the original file.
        image = ImageOps.fit(ImageOps.exif_transpose(Image.open(photo)).convert("RGB"), (400, 400))
        out = io.BytesIO()
        image.save(out, "JPEG", quality=85)
        return ContentFile(out.getvalue(), name="photo.jpg")

    def save(self, commit=True):
        page = super().save(commit=False)
        if self.cleaned_data.get("remove_avatar"):
            page.avatar.delete(save=False)
            page.avatar = ""
        if commit:
            page.save()
        return page


class AppearanceForm(forms.ModelForm):
    class Meta:
        model = Page
        fields = ["theme", "button_style", "bg_color", "text_color", "button_color", "button_text_color"]
        labels = {"bg_color": "Background", "text_color": "Text", "button_color": "Buttons", "button_text_color": "Button text"}
        widgets = {
            "theme": forms.RadioSelect,
            "button_style": forms.RadioSelect,
            **{f: forms.TextInput(attrs={"type": "color"}) for f in ["bg_color", "text_color", "button_color", "button_text_color"]},
        }

    def clean(self):
        data = super().clean()
        for field in ["bg_color", "text_color", "button_color", "button_text_color"]:
            if data.get(field) and not COLOR_RE.match(data[field]):
                self.add_error(field, "Pick a colour.")
        return data


class SocialsForm(forms.ModelForm):
    class Meta:
        model = Page
        fields = [field for field, _, _ in SOCIALS]
        labels = {field: label for field, label, _ in SOCIALS}
        help_texts = {"whatsapp": "Number with country code, e.g. 8801712345678", "website": "Full address, https://…"}

    def clean_whatsapp(self):
        number = re.sub(r"\D", "", self.cleaned_data["whatsapp"])
        if number and not 8 <= len(number) <= 15:
            raise forms.ValidationError("Type the full number with country code.")
        return number


class SettingsForm(HandleMixin, forms.ModelForm):
    class Meta:
        model = Page
        fields = ["handle", "is_published", "sensitive", "collect_emails", "email_prompt"]
        labels = {
            "handle": "Page name", "is_published": "Page is public", "sensitive": "Show a sensitive-content warning first",
            "collect_emails": "Collect email sign-ups", "email_prompt": "Sign-up form title",
        }


class ItemForm(forms.ModelForm):
    url = forms.URLField(required=False, max_length=2000, assume_scheme="https", label="Address")

    class Meta:
        model = Item
        fields = ["kind", "title", "url", "show_from", "show_until", "is_active"]
        labels = {"kind": "Type", "show_from": "Show from", "show_until": "Hide after", "is_active": "Show it"}
        help_texts = {"show_from": "Optional: schedule when it appears.", "show_until": "Optional: when it disappears."}
        widgets = {"show_from": DATETIME, "show_until": DATETIME}

    def clean(self):
        data = super().clean()
        kind, url = data.get("kind"), (data.get("url") or "").strip()
        if kind == Item.HEADER:
            data["url"] = ""
        elif not url:
            self.add_error("url", "Add the address.")
        elif not url.startswith(("http://", "https://")):
            self.add_error("url", "Only web addresses (http or https).")
        elif kind == Item.VIDEO and not Item(url=url).youtube_id:
            self.add_error("url", "Paste a YouTube video address.")
        start, end = data.get("show_from"), data.get("show_until")
        if start and end and end <= start:
            self.add_error("show_until", "Pick a time after 'Show from'.")
        return data


class SubscribeForm(forms.Form):
    email = forms.EmailField(max_length=254)
    website = forms.CharField(required=False)  # honeypot: people never see or fill it

    def is_spam(self):
        return bool(self.cleaned_data.get("website"))
