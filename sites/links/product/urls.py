from django.contrib import admin
from django.conf import settings
from django.urls import include, path, re_path
from django.views.static import serve

from bio import views as bio
from dashboard.admin_signin import admin_login
from shortener import views as shortener

# The admin pages sign in with the Marketian account, like everything else (no admin password).
admin.site.login = admin_login

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("app/page/", include("bio.urls")),
    path("app/", include("shortener.urls")),
    # Bio page photos (WhiteNoise only serves the app's own files).
    re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}),
    path("", include("dashboard.urls")),
    # Bio pages: /@name, its buttons /@name/go/<id>, the email sign-up form.
    re_path(r"^@(?P<handle>[A-Za-z0-9_.]+)/?$", bio.public, name="bio_page"),
    re_path(r"^@(?P<handle>[A-Za-z0-9_.]+)/go/(?P<pk>\d+)/?$", bio.follow, name="bio_follow"),
    re_path(r"^@(?P<handle>[A-Za-z0-9_.]+)/subscribe/?$", bio.subscribe, name="bio_subscribe"),
    # Short links: /name follows the link, /name+ shows where it goes.
    re_path(r"^(?P<slug>[A-Za-z0-9_-]+)\+$", shortener.preview, name="preview"),
    re_path(r"^(?P<slug>[A-Za-z0-9_-]+)/?$", shortener.follow, name="follow"),
]
