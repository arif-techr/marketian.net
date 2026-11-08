from django.contrib import admin

from .models import Item, Page


class ItemInline(admin.TabularInline):
    model = Item
    extra = 0
    fields = ["position", "kind", "title", "url", "is_active", "clicks"]
    readonly_fields = ["clicks"]


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    """Unpublish any page used for spam or scams (is_published)."""

    list_display = ["handle", "title", "owner", "views", "is_published", "created_at"]
    list_editable = ["is_published"]
    list_filter = ["is_published", "sensitive"]
    search_fields = ["handle", "title", "owner__email"]
    readonly_fields = ["views", "created_at", "updated_at"]
    inlines = [ItemInline]
