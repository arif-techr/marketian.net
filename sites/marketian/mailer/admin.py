from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.urls import path, reverse
from django.utils.html import escape, format_html

from .models import EmailSignature, EmailTemplate, SentEmail
from .services import build_email, fill, placeholder_context, send_email
from .views import compose


def preview_frame(html, height=420):
    return format_html(
        '<iframe srcdoc="{}" style="width:100%;max-width:720px;height:{}px;border:1px solid #ddd;'
        'border-radius:8px;background:#fff"></iframe>', escape(html), height,
    )


def test_recipient(request):
    return [request.user.email] if request.user.email else settings.CONTACT_RECIPIENTS[:1]


@admin.register(EmailSignature)
class EmailSignatureAdmin(admin.ModelAdmin):
    list_display = ["label", "sign_off", "company", "is_default"]
    readonly_fields = ["preview", "html_code"]
    actions = ["send_test"]
    fieldsets = [
        (None, {"fields": ["label", "is_default"]}),
        ("Signature", {"fields": ["sign_off", "full_name", "job_title", "company", "email", "phone", "website",
                                  "show_photo", "show_socials", "accent_color", "disclaimer"]}),
        ("Preview (save to refresh)", {"fields": ["preview", "html_code"]}),
    ]

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == "accent_color":
            kwargs["widget"] = forms.TextInput(attrs={"type": "color"})
        return super().formfield_for_dbfield(db_field, request, **kwargs)

    @admin.display(description="Preview")
    def preview(self, obj):
        return preview_frame(obj.render_html(), 200) if obj.pk else "Save first to see the preview."

    @admin.display(description="HTML (paste into Gmail / Outlook)")
    def html_code(self, obj):
        if not obj.pk:
            return "-"
        return format_html(
            '<textarea readonly rows="6" style="width:100%;max-width:720px;font-family:monospace;font-size:12px" '
            'onclick="this.select()">{}</textarea><p class="help">Gmail: open the preview above, select it all, '
            'copy and paste into Settings → Signature. Other apps that accept HTML can use this code.</p>',
            obj.render_html(),
        )

    @admin.action(description="Send a test email to myself")
    def send_test(self, request, queryset):
        for sig in queryset:
            log = send_email(to=test_recipient(request), subject=f"Signature test: {sig.label}", kind="test",
                             body="This is how your signature looks in a real email.", signature=sig, user=request.user)
            self.message_user(request, f"{sig.label}: {log.get_status_display()} → {log.to}",
                              messages.SUCCESS if log.status == SentEmail.SENT else messages.ERROR)


@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = ["name", "purpose", "subject", "is_active", "updated_at"]
    list_filter = ["purpose", "is_active"]
    list_editable = ["is_active"]
    search_fields = ["name", "subject", "body"]
    readonly_fields = ["preview"]
    actions = ["send_test", "duplicate"]
    fields = ["name", "purpose", "is_active", "subject", "body", "signature", "preview"]

    @admin.display(description="Preview (sample data, save to refresh)")
    def preview(self, obj):
        if not obj.pk:
            return "Save first to see the preview."
        ctx = placeholder_context(name="Jane Doe", email="jane@example.com")
        ctx.update(subject="New website for my shop", message="Hi! I'd like a new website for my shop.")
        _, html = build_email(fill(obj.body, ctx), signature=obj.signature)
        return format_html("<p><strong>Subject:</strong> {}</p>{}", fill(obj.subject, ctx), preview_frame(html, 560))

    @admin.action(description="Send a test (sample data) to myself")
    def send_test(self, request, queryset):
        ctx = placeholder_context(name="Jane Doe", email="jane@example.com")
        for tpl in queryset:
            log = send_email(to=test_recipient(request), subject="[TEST] " + fill(tpl.subject, ctx), kind="test",
                             body=fill(tpl.body, ctx), signature=tpl.signature, template=tpl, user=request.user)
            self.message_user(request, f"{tpl.name}: {log.get_status_display()} → {log.to}",
                              messages.SUCCESS if log.status == SentEmail.SENT else messages.ERROR)

    @admin.action(description="Duplicate selected templates")
    def duplicate(self, request, queryset):
        for tpl in queryset:
            tpl.pk, tpl.name, tpl.is_active = None, f"{tpl.name} (copy)", tpl.purpose != EmailTemplate.AUTO_REPLY
            tpl.save()


@admin.register(SentEmail)
class SentEmailAdmin(admin.ModelAdmin):
    change_list_template = "admin/mailer/sentemail/change_list.html"
    list_display = ["subject", "to", "kind", "status", "created_at"]
    list_filter = ["kind", "status", "created_at"]
    search_fields = ["to", "subject", "body"]
    readonly_fields = ["kind", "status", "to", "cc", "subject", "template", "contact", "sent_by", "created_at", "error", "preview"]
    fields = readonly_fields

    @admin.display(description="Email")
    def preview(self, obj):
        return preview_frame(obj.html, 600) if obj.html else obj.body

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False  # read-only log; the view permission still opens each email

    def get_urls(self):
        return [path("compose/", self.admin_site.admin_view(compose), name="mailer_compose")] + super().get_urls()

    def changelist_view(self, request, extra_context=None):
        extra_context = {**(extra_context or {}), "compose_url": reverse("admin:mailer_compose")}
        return super().changelist_view(request, extra_context)
