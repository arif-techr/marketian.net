from django import forms
from django.core.validators import validate_email

from .models import EmailSignature, EmailTemplate, PLACEHOLDER_HELP, validate_placeholders


def parse_emails(value):
    emails = [e.strip() for e in value.replace(";", ",").split(",") if e.strip()]
    for email in emails:
        try:
            validate_email(email)
        except forms.ValidationError:
            raise forms.ValidationError(f"“{email}” is not a valid email address.")
    return emails


class ComposeForm(forms.Form):
    to = forms.CharField(help_text="Separate several addresses with commas.")
    recipient_name = forms.CharField(required=False, help_text="Used for {{ name }} and {{ first_name }}.")
    cc = forms.CharField(required=False, label="CC")
    template = forms.ModelChoiceField(
        EmailTemplate.objects.exclude(purpose=EmailTemplate.AUTO_REPLY).filter(is_active=True),
        required=False, empty_label="— Start from a template —",
    )
    signature = forms.ModelChoiceField(EmailSignature.objects.all(), required=False, empty_label="Default signature")
    no_signature = forms.BooleanField(required=False, label="Send without a signature")
    subject = forms.CharField(max_length=200, validators=[validate_placeholders])
    body = forms.CharField(widget=forms.Textarea(attrs={"rows": 16}), validators=[validate_placeholders], help_text=PLACEHOLDER_HELP)
    include_original = forms.BooleanField(required=False, initial=True, label="Quote their original message under my reply")

    def __init__(self, *args, contact=None, **kwargs):
        super().__init__(*args, **kwargs)
        if contact:
            del self.fields["recipient_name"]
        else:
            del self.fields["include_original"]

    def clean_to(self):
        emails = parse_emails(self.cleaned_data["to"])
        if not emails:
            raise forms.ValidationError("Add at least one recipient.")
        return emails

    def clean_cc(self):
        return parse_emails(self.cleaned_data["cc"])


class BulkSendForm(forms.Form):
    template = forms.ModelChoiceField(EmailTemplate.objects.exclude(purpose=EmailTemplate.AUTO_REPLY).filter(is_active=True))
    signature = forms.ModelChoiceField(EmailSignature.objects.all(), required=False, empty_label="Template's / default signature")
