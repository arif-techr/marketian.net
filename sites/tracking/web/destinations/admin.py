from django.contrib import admin

from .models import Destination


@admin.register(Destination)
class DestinationAdmin(admin.ModelAdmin):
    list_display = ("label", "type", "site", "enabled", "health", "last_success_at")
    list_filter = ("type", "enabled", "health")
    search_fields = ("label", "site__name")
    # The secret is only ever set through the dashboard; here you see its hint, never the value.
    readonly_fields = ("masked_secret", "health", "last_error", "last_success_at", "created_at", "updated_at")
    exclude = ("secret_enc", "secret_hint")
