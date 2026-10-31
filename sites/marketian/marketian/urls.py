from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path, re_path
from django.views.static import serve

from core.sitemaps import ProjectSitemap, StaticSitemap

handler404 = "core.views.page_not_found"

admin.site.site_header = "Marketian Admin"
admin.site.site_title = "Marketian Admin"
admin.site.index_title = "Manage your portfolio"

sitemaps = {"static": StaticSitemap, "projects": ProjectSitemap}

urlpatterns = [
    path("admin/", admin.site.urls),
    path("sitemap.xml", sitemap, {"sitemaps": sitemaps}, name="sitemap"),
    path("", include("core.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
elif settings.SERVE_MEDIA:
    # For simple hosts with no web server in front for /media/ (uploaded photos, CV).
    urlpatterns += [re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT})]
