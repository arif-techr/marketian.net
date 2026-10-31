from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Marketian Accounts"
admin.site.site_title = "Marketian Accounts"
admin.site.index_title = "Users and products"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("o/", include("oauth2_provider.urls", namespace="oauth2_provider")),
    path("", include("portal.urls")),
]
