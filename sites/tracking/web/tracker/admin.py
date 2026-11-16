from django.contrib import admin

from .models import ApiKey, Domain, Site


class DomainInline(admin.TabularInline):
    model = Domain
    extra = 0
    fields = ("hostname", "mode", "status", "verified_at", "fail_count")
    readonly_fields = ("verified_at", "fail_count")


@admin.register(Site)
class SiteAdmin(admin.ModelAdmin):
    list_display = ("name", "primary_domain", "workspace", "status", "path_prefix", "created_at")
    list_filter = ("status", "consent_mode")
    search_fields = ("name", "primary_domain", "public_key")
    readonly_fields = ("public_key", "path_prefix", "loader_name", "config_version", "created_by", "created_at", "updated_at")
    inlines = [DomainInline]


@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display = ("hostname", "site", "mode", "status", "last_checked_at")
    list_filter = ("status", "mode")
    search_fields = ("hostname",)


@admin.register(ApiKey)
class ApiKeyAdmin(admin.ModelAdmin):
    list_display = ("prefix", "name", "site", "last_used_at", "revoked_at")
    readonly_fields = ("prefix", "key_hash", "last_used_at", "created_by", "created_at")
    search_fields = ("prefix", "name")
