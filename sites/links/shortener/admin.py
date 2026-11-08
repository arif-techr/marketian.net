from django.contrib import admin

from .models import Link


@admin.register(Link)
class LinkAdmin(admin.ModelAdmin):
    """Turn off any link that's used for spam or phishing (is_active)."""

    list_display = ["slug", "destination", "owner", "clicks", "is_active", "created_at"]
    list_editable = ["is_active"]
    list_filter = ["is_active"]
    search_fields = ["slug", "destination", "title", "owner__email"]
    readonly_fields = ["clicks", "created_at", "updated_at"]
    exclude = ["password"]
