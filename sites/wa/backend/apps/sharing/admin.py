from django.contrib import admin

from .models import Share, ShareInvite


@admin.register(ShareInvite)
class ShareInviteAdmin(admin.ModelAdmin):
    list_display = ["id", "owner", "to_user", "status", "expires_at", "created_at"]
    list_filter = ["status"]
    readonly_fields = ["code_digest", "attempts", "accepted_at"]


@admin.register(Share)
class ShareAdmin(admin.ModelAdmin):
    list_display = ["id", "owner", "grantee", "account", "contact_list", "template", "created_at"]
    list_filter = ["owner", "grantee"]
