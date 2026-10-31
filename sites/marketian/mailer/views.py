"""Admin-only pages: compose / reply with preview, and the bulk-send step."""

from django.contrib import admin, messages
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import reverse

from core.models import ContactMessage

from .forms import BulkSendForm, ComposeForm
from .models import PLACEHOLDER_HELP, EmailTemplate, SentEmail
from .services import build_email, fill, placeholder_context, send_email, send_from_template


def compose(request, contact_id=None):
    contact = get_object_or_404(ContactMessage, pk=contact_id) if contact_id else None
    preview_html = None

    if request.method == "POST":
        form = ComposeForm(request.POST, contact=contact)
        if form.is_valid():
            d = form.cleaned_data
            ctx = placeholder_context(contact, name=d.get("recipient_name", ""), email=d["to"][0])
            subject, body = fill(d["subject"], ctx), fill(d["body"], ctx)
            include_original = bool(contact and d.get("include_original"))
            if "_send" in request.POST:
                log = send_email(
                    to=d["to"], cc=d["cc"], subject=subject, body=body, kind="reply" if contact else "compose",
                    signature=d["signature"], use_signature=not d["no_signature"], contact=contact,
                    template=d["template"], user=request.user, include_original=include_original,
                )
                if log.status == SentEmail.SENT:
                    messages.success(request, f"Email sent to {log.to}.")
                    if contact:
                        return redirect("admin:core_contactmessage_change", contact.pk)
                    return redirect("admin:mailer_sentemail_changelist")
                messages.error(request, f"Sending failed: {log.error}. Check the EMAIL_* settings in .env.")
            _, preview_html = build_email(
                body, signature=d["signature"], use_signature=not d["no_signature"],
                original=contact if include_original else None,
            )
    else:
        template = None
        if request.GET.get("template"):
            template = EmailTemplate.objects.filter(pk=request.GET["template"]).first()
        elif contact:
            template = EmailTemplate.objects.filter(purpose=EmailTemplate.REPLY, is_active=True).first()
        form = ComposeForm(contact=contact, initial={
            "to": contact.email if contact else request.GET.get("to", ""),
            "template": template,
            "signature": template.signature if template else None,
            "subject": template.subject if template else (f"Re: {contact.subject}" if contact else ""),
            "body": template.body if template else "",
            "include_original": True,
        })

    templates_data = {
        str(t.pk): {"subject": t.subject, "body": t.body, "signature": t.signature_id}
        for t in form.fields["template"].queryset
    }
    return TemplateResponse(request, "admin/mailer/compose.html", {
        **admin.site.each_context(request),
        "title": f"Reply to {contact.name}" if contact else "Compose email",
        "form": form,
        "contact": contact,
        "preview_html": preview_html,
        "templates_data": templates_data,
        "placeholder_help": PLACEHOLDER_HELP,
        "sample": placeholder_context(contact),
        "opts": ContactMessage._meta if contact else SentEmail._meta,
    })


def bulk_send(modeladmin, request, queryset):
    """Admin action step: choose a template, then send a personalised copy to each selected contact."""
    if "_apply" in request.POST:
        form = BulkSendForm(request.POST)
        if form.is_valid():
            sent = failed = 0
            for contact in queryset:
                log = send_from_template(form.cleaned_data["template"], contact,
                                         signature=form.cleaned_data["signature"], user=request.user)
                sent, failed = (sent + 1, failed) if log.status == SentEmail.SENT else (sent, failed + 1)
            if sent:
                messages.success(request, f"Sent {sent} email(s).")
            if failed:
                messages.error(request, f"{failed} email(s) failed — see Mail → Sent emails.")
            return None
    else:
        form = BulkSendForm()
    return TemplateResponse(request, "admin/mailer/bulk_send.html", {
        **admin.site.each_context(request),
        "title": "Send a template email",
        "form": form,
        "queryset": queryset,
        "opts": modeladmin.model._meta,
        "action_name": request.POST.get("action"),
        "changelist_url": reverse("admin:core_contactmessage_changelist"),
    })
