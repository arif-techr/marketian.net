from django.contrib import admin
from django.shortcuts import redirect
from django.urls import path, reverse
from django.utils.html import format_html

from mailer.views import bulk_send, compose

from .models import ContactMessage, Experience, Project, Service, SiteProfile, Skill, Testimonial, Tool


@admin.register(SiteProfile)
class SiteProfileAdmin(admin.ModelAdmin):
    fieldsets = [
        ("Identity", {"fields": ["name", "role", "tagline", "photo", "resume", "available_for_work"]}),
        ("About", {"fields": ["short_bio", "about"]}),
        ("Stats", {"fields": ["years_experience", "projects_completed", "happy_clients"]}),
        ("Contact", {"fields": ["email", "phone", "whatsapp", "location"]}),
        ("Social links", {"fields": ["linkedin", "github", "facebook", "twitter", "instagram", "youtube"]}),
    ]

    def has_add_permission(self, request):
        return not SiteProfile.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        profile = SiteProfile.load()
        return redirect(reverse("admin:core_siteprofile_change", args=[profile.pk]))


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ["title", "icon", "order", "is_active"]
    list_editable = ["order", "is_active"]


@admin.register(Tool)
class ToolAdmin(admin.ModelAdmin):
    list_display = ["name", "status", "url", "order", "is_active"]
    list_editable = ["status", "order", "is_active"]


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ["title", "category", "client", "featured", "is_published", "order"]
    list_editable = ["featured", "is_published", "order"]
    list_filter = ["category", "featured", "is_published"]
    search_fields = ["title", "client", "summary", "tags"]
    prepopulated_fields = {"slug": ["title"]}


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ["name", "group", "level", "order"]
    list_editable = ["level", "order"]
    list_filter = ["group"]


@admin.register(Experience)
class ExperienceAdmin(admin.ModelAdmin):
    list_display = ["title", "organization", "period", "order"]
    list_editable = ["order"]


@admin.register(Testimonial)
class TestimonialAdmin(admin.ModelAdmin):
    list_display = ["name", "position", "order", "is_active"]
    list_editable = ["order", "is_active"]


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    change_form_template = "admin/core/contactmessage/change_form.html"
    list_display = ["name", "email", "subject", "budget", "created_at", "is_read", "replied", "reply_link"]
    list_filter = ["is_read", "replied_at", "email_sent", "created_at"]
    search_fields = ["name", "email", "subject", "message"]
    readonly_fields = ["name", "email", "phone", "subject", "budget", "message", "ip_address", "created_at",
                       "email_sent", "replied_at", "email_history"]
    actions = ["send_template_email", "mark_read", "mark_unread"]

    def has_add_permission(self, request):
        return False

    def get_urls(self):
        return [
            path("<int:contact_id>/reply/", self.admin_site.admin_view(compose), name="core_contactmessage_reply"),
        ] + super().get_urls()

    def change_view(self, request, object_id, form_url="", extra_context=None):
        ContactMessage.objects.filter(pk=object_id).update(is_read=True)
        extra_context = {**(extra_context or {}), "reply_url": reverse("admin:core_contactmessage_reply", args=[object_id])}
        return super().change_view(request, object_id, form_url, extra_context)

    @admin.display(boolean=True, description="Replied", ordering="replied_at")
    def replied(self, obj):
        return obj.replied_at is not None

    @admin.display(description="")
    def reply_link(self, obj):
        return format_html('<a class="button" href="{}">✉ Reply</a>', reverse("admin:core_contactmessage_reply", args=[obj.pk]))

    @admin.display(description="Emails")
    def email_history(self, obj):
        rows = [
            format_html('<li><a href="{}">{}</a> — {} · {} · {}</li>',
                        reverse("admin:mailer_sentemail_change", args=[e.pk]), e.subject,
                        e.get_kind_display(), e.get_status_display(), e.created_at.strftime("%d %b %Y %H:%M"))
            for e in obj.emails.all()
        ]
        return format_html("<ul style='margin:0;padding-left:18px'>{}</ul>", format_html("".join(rows))) if rows else "—"

    @admin.action(description="✉ Send a template email to selected")
    def send_template_email(self, request, queryset):
        return bulk_send(self, request, queryset)

    @admin.action(description="Mark selected as read")
    def mark_read(self, request, queryset):
        queryset.update(is_read=True)

    @admin.action(description="Mark selected as unread")
    def mark_unread(self, request, queryset):
        queryset.update(is_read=False)
