from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import ContactMessage, SiteProfile

from .models import EmailSignature, EmailTemplate, SentEmail
from .services import fill, placeholder_context


@override_settings(CONTACT_RECIPIENTS=["owner@marketian.net"], SITE_URL="https://marketian.net")
class MailerTests(TestCase):
    def setUp(self):
        profile = SiteProfile.load()
        profile.name, profile.email = "Ariful Islam", "hello@marketian.net"
        profile.save()
        self.admin = User.objects.create_superuser("admin", "admin@marketian.net", "pass12345")
        self.client.force_login(self.admin)
        self.contact = ContactMessage.objects.create(
            name="Jane Doe", email="jane@example.com", subject="New website", message="Need a shop site.",
        )

    def test_defaults_created_by_migration(self):
        self.assertTrue(EmailSignature.objects.filter(is_default=True).exists())
        self.assertTrue(EmailTemplate.objects.filter(purpose="auto_reply", is_active=True).exists())

    def test_visitor_message_notifies_owner_and_auto_replies(self):
        self.client.logout()
        self.client.post(reverse("core:contact"), {
            "name": "Bob Smith", "email": "bob@example.com", "subject": "SEO help",
            "message": "Can you help with SEO for my store?",
        })
        self.assertEqual([m.to for m in mail.outbox], [["owner@marketian.net"], ["bob@example.com"]])
        self.assertIn("Bob", mail.outbox[1].subject)
        self.assertIn("/admin/core/contactmessage/", mail.outbox[0].body)
        self.assertEqual(SentEmail.objects.filter(status="sent").count(), 2)

    def test_placeholders_do_not_execute_visitor_input(self):
        self.contact.message = "{% debug %}{{ my_email }}"
        ctx = placeholder_context(self.contact)
        self.assertEqual(fill("Hi {{ first_name }}: {{ message }}", ctx), "Hi Jane: {% debug %}{{ my_email }}")

    def test_reply_page_preview_and_send(self):
        url = reverse("admin:core_contactmessage_reply", args=[self.contact.pk])
        self.assertContains(self.client.get(url), "Reply to Jane Doe")
        data = {"to": "jane@example.com", "cc": "", "subject": "Re: {{ subject }}",
                "body": "Hi {{ first_name }}, happy to help.", "signature": "", "include_original": "on"}
        preview = self.client.post(url, {**data, "_preview": "1"})
        self.assertContains(preview, "Hi Jane, happy to help.")
        self.assertEqual(len(mail.outbox), 0)

        self.client.post(url, {**data, "_send": "1"})
        sent = mail.outbox[0]
        self.assertEqual(sent.subject, "Re: New website")
        self.assertIn("Best regards,", sent.body)
        self.assertIn("Need a shop site.", sent.body)
        html = sent.alternatives[0][0]
        self.assertIn("Ariful Islam", html)
        self.contact.refresh_from_db()
        self.assertIsNotNone(self.contact.replied_at)

    def test_compose_to_anyone(self):
        self.client.post(reverse("admin:mailer_compose"), {
            "to": "a@example.com, b@example.com", "recipient_name": "Sam Lee", "subject": "Hello",
            "body": "Hi {{ first_name }}!", "_send": "1",
        })
        self.assertEqual(mail.outbox[0].to, ["a@example.com", "b@example.com"])
        self.assertIn("Hi Sam!", mail.outbox[0].body)

    def test_bulk_template_send(self):
        other = ContactMessage.objects.create(name="Tom Ray", email="tom@example.com", subject="Ads", message="x" * 20)
        tpl = EmailTemplate.objects.filter(purpose="reply").first()
        self.client.post(reverse("admin:core_contactmessage_changelist"), {
            "action": "send_template_email", "_selected_action": [self.contact.pk, other.pk],
            "template": tpl.pk, "_apply": "1",
        })
        self.assertEqual(sorted(m.to[0] for m in mail.outbox), ["jane@example.com", "tom@example.com"])
        self.assertTrue(any("Hi Tom," in m.body for m in mail.outbox))

    def test_admin_pages_render(self):
        sig = EmailSignature.get_default()
        tpl = EmailTemplate.objects.first()
        for url in [
            reverse("admin:mailer_emailsignature_change", args=[sig.pk]),
            reverse("admin:mailer_emailtemplate_change", args=[tpl.pk]),
            reverse("admin:mailer_sentemail_changelist"),
            reverse("admin:core_contactmessage_change", args=[self.contact.pk]),
            reverse("admin:core_contactmessage_changelist"),
        ]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    @override_settings(EMAIL_BACKEND="mailer.tests.FailingBackend")
    def test_failed_send_is_logged(self):
        url = reverse("admin:core_contactmessage_reply", args=[self.contact.pk])
        response = self.client.post(url, {"to": "jane@example.com", "subject": "x", "body": "y", "_send": "1"})
        self.assertContains(response, "Sending failed")
        self.assertEqual(SentEmail.objects.get().status, "failed")


class FailingBackend:
    def __init__(self, *args, **kwargs):
        pass

    def send_messages(self, messages):
        raise ConnectionError("SMTP down")
