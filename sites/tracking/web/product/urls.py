from django.contrib import admin
from django.urls import include, path

from dashboard.admin_signin import admin_login

# The admin pages sign in with the Marketian account, like everything else (no admin password).
admin.site.login = admin_login

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("sites/", include("tracker.urls")),
    path("internal/", include("internal.urls")),
    path("", include("dashboard.urls")),
]
