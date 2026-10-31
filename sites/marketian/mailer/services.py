"""Building and sending branded emails. Every send is logged as a SentEmail."""

import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template import Context, Engine, TemplateSyntaxError
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.dateformat import format as date_format
from django.utils.html import linebreaks, urlize
from django.utils.safestring import mark_safe

from core.models import SiteProfile

from .models import EmailSignature, EmailTemplate, SentEmail

logger = logging.getLogger(__name__)
_engine = Engine(autoescape=False)


def site_url(path=""):
    return settings.SITE_URL.rstrip("/") + path


def placeholder_context(contact=None, name="", email=""):
    p = SiteProfile.load()
    name = (contact.name if contact else name).strip()
    return {
        "name": name or "there",
        "first_name": name.split()[0] if name else "there",
        "email": contact.email if contact else email,
        "subject": contact.subject if contact else "",
        "message": contact.message if contact else "",
        "my_name": p.name,
        "my_role": p.role,
        "my_email": p.email,
        "my_phone": p.phone,
        "website": settings.SITE_URL,
        "today": date_format(timezone.localdate(), "j F Y"),
    }


def fill(text, context):
    """Replace {{ placeholders }}. Visitor data is only ever passed as context, never as template source."""
    try:
        return _engine.from_string(text).render(Context(context))
    except TemplateSyntaxError:
        return text


def text_to_html(text):
    html = linebreaks(urlize(text, autoescape=True))
    return mark_safe(html.replace("<p>", '<p style="margin:0 0 16px;">'))


def build_email(body, *, signature=None, use_signature=True, original=None, heading=""):
    """Return (plain_text, html) for a message body."""
    profile = SiteProfile.load()
    sig = (signature or EmailSignature.get_default()) if use_signature else None

    text = body.rstrip()
    if sig:
        text += "\n\n" + sig.render_text()
    if original:
        quoted = "\n".join("> " + line for line in original.message.splitlines())
        text += (
            f"\n\n----- Original message -----\nFrom: {original.name} <{original.email}>\n"
            f"Date: {date_format(timezone.localtime(original.created_at), 'j M Y, H:i')}\n"
            f"Subject: {original.subject}\n\n{quoted}"
        )

    html = render_to_string("mailer/email.html", {
        "heading": heading,
        "body_html": text_to_html(body.rstrip()),
        "signature_html": mark_safe(sig.render_html()) if sig else "",
        "original": original,
        "profile": profile,
        "site_url": settings.SITE_URL,
        "site_host": settings.SITE_URL.split("://")[-1].rstrip("/"),
    })
    return text, html


def send_email(*, to, subject, body, kind, signature=None, use_signature=True, contact=None,
               template=None, user=None, cc=None, include_original=False, reply_to=None, heading=""):
    """Send one email (text + HTML) and log it. Never raises; check `.status` on the result."""
    to, cc = list(to), list(cc or [])
    text, html = build_email(
        body, signature=signature, use_signature=use_signature,
        original=contact if include_original else None, heading=heading,
    )
    log = SentEmail(
        kind=kind, to=", ".join(to), cc=", ".join(cc), subject=subject, body=text, html=html,
        template=template, contact=contact, sent_by=user if user and user.is_authenticated else None,
    )
    message = EmailMultiAlternatives(
        subject=subject, body=text, from_email=settings.DEFAULT_FROM_EMAIL, to=to, cc=cc,
        reply_to=reply_to or [SiteProfile.load().email],
    )
    message.attach_alternative(html, "text/html")
    try:
        message.send(fail_silently=False)
        log.status = SentEmail.SENT
    except Exception as exc:
        logger.exception("Email sending failed")
        log.status, log.error = SentEmail.FAILED, str(exc)
    log.save()

    if contact and kind in ("reply", "bulk") and log.status == SentEmail.SENT:
        contact.replied_at = timezone.now()
        contact.is_read = True
        contact.save(update_fields=["replied_at", "is_read"])
    return log


def send_from_template(template, contact, *, signature=None, user=None, kind="bulk"):
    ctx = placeholder_context(contact)
    return send_email(
        to=[contact.email], subject=fill(template.subject, ctx), body=fill(template.body, ctx), kind=kind,
        signature=signature or template.signature, contact=contact, template=template, user=user,
    )


def notify_new_contact(contact):
    """Email the site owner about a new message, then auto-reply to the visitor if enabled."""
    recipients = settings.CONTACT_RECIPIENTS or [SiteProfile.load().email]
    body = render_to_string("emails/contact_notification.txt", {
        "m": contact,
        "reply_url": site_url(reverse("admin:core_contactmessage_reply", args=[contact.pk])),
    })
    log = send_email(
        to=recipients, subject=f"[Marketian] {contact.subject}", body=body, kind="notification",
        use_signature=False, contact=contact, reply_to=[contact.email], heading="New message from your website",
    )
    if log.status == SentEmail.SENT:
        contact.email_sent = True
        contact.save(update_fields=["email_sent"])

    auto = EmailTemplate.objects.filter(purpose=EmailTemplate.AUTO_REPLY, is_active=True).first()
    if auto:
        send_from_template(auto, contact, kind="auto_reply")
