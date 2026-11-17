from django.contrib import admin
from django.urls import include, path

from common import views as common

handler404 = "common.views.not_found"
handler500 = "common.views.server_error"

urlpatterns = [
    path("api/v1/health", common.health, name="health"),
    path("accounts/", include("allauth.urls")),
    path("django-admin/", admin.site.urls),
]
