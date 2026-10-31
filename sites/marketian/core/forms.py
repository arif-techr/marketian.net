from django import forms

from .models import ContactMessage

BUDGET_CHOICES = [
    ("", "Select a budget (optional)"),
    ("< $500", "Less than $500"),
    ("$500 – $1,500", "$500 – $1,500"),
    ("$1,500 – $5,000", "$1,500 – $5,000"),
    ("$5,000+", "$5,000+"),
]


class ContactForm(forms.ModelForm):
    budget = forms.ChoiceField(choices=BUDGET_CHOICES, required=False)
    # Honeypot: real visitors never see or fill this field.
    website = forms.CharField(required=False, widget=forms.TextInput(attrs={"tabindex": "-1", "autocomplete": "off"}))

    class Meta:
        model = ContactMessage
        fields = ["name", "email", "phone", "subject", "budget", "message"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Your full name", "autocomplete": "name"}),
            "email": forms.EmailInput(attrs={"placeholder": "you@example.com", "autocomplete": "email"}),
            "phone": forms.TextInput(attrs={"placeholder": "+880 1XXX-XXXXXX (optional)", "autocomplete": "tel"}),
            "subject": forms.TextInput(attrs={"placeholder": "What is this about?"}),
            "message": forms.Textarea(attrs={"rows": 6, "placeholder": "Tell me about your project, goals and timeline…"}),
        }

    def clean_message(self):
        message = self.cleaned_data["message"].strip()
        if len(message) < 10:
            raise forms.ValidationError("Please write a little more so I can help (at least 10 characters).")
        return message

    def is_spam(self):
        return bool(self.cleaned_data.get("website"))
